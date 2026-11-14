"""Offline contracts for the async Uconnect integration; no account or vehicle calls."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from py_uconnect import (
    APIError, AuthenticationError, Client, CommandError, CommandTimeoutError,
    UconnectConnectionError, PinAuthenticationError, brands,
)
from py_uconnect.command import COMMAND_DOORS_LOCK

ROOT = Path(__file__).resolve().parents[1]
VIN = "F" * 17
OTHER = "E" * 17
ENTRY = {
    "vin": VIN, "nickname": "500", "make": "Fixture", "modelDescription": "Pickup",
    "year": 2022, "soldRegion": "US", "sdp": "ignite",
    "services": [{"service": "CPCOOP", "vehicleCapable": True, "serviceEnabled": True}],
}
INFO = {"vehicleInfo": {
    "odometer": {"odometer": {"value": 5000, "unit": "mi"}},
    "fuel": {"fuelAmountLevel": 67, "distanceToEmpty": {"value": 300, "unit": "mi"}},
    "batteryInfo": {"batteryVoltage": {"value": 12.6}},
    "oilLevel": {"oilLevel": 80},
    "tyrePressure": [
        {"type": key, "pressure": {"value": 65, "unit": "psi"}, "warning": False}
        for key in ("FL", "FR", "RL", "RR")
    ],
}, "evInfo": {"battery": {"distanceToEmpty": {"value": 0, "unit": "mi"}}}}
STATUS = {"doors": {
    key: {"status": "LOCKED"} for key in ("driver", "passenger", "leftRear", "rightRear")
}, "engine": {"status": "OFF"}}


def load(name):
    spec = importlib.util.spec_from_file_location("truck_" + name, ROOT / "scripts" / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def client():
    """Use the real async Client lifecycle, replacing only the remote API boundary."""
    instance = Client("fixture@example.invalid", "fixture-password", "0000", brand=brands.RAM_US)
    instance.api = SimpleNamespace(
        close=AsyncMock(),
        list_vehicles=AsyncMock(return_value=[ENTRY]),
        get_vehicle_info=AsyncMock(return_value=INFO),
        get_remote_status=AsyncMock(return_value=STATUS),
        get_vehicle_location=AsyncMock(side_effect=APIError("fixture unavailable", status=404)),
        command=AsyncMock(return_value="fixture-operation"),
        get_remote_operation_last_status=AsyncMock(return_value={"status": "succeeded"}),
        get_remote_operation_status=AsyncMock(return_value={}),
        get_vehicle_notifications=AsyncMock(return_value={}),
    )
    return instance


class Imports(unittest.TestCase):
    def test_entrypoints_import_with_the_pinned_library(self):
        for name in ("poll", "send_command", "reset_oil_baseline", "probe_capabilities", "test_connection"):
            with self.subTest(script=name):
                try:
                    load(name)
                except ImportError as exc:
                    self.fail(f"{name} cannot use the pinned async library: {exc}")

    def test_cli_missing_credentials_never_connects(self):
        env = dict(os.environ, MOPAR_EMAIL="", MOPAR_PASSWORD="", MOPAR_PIN="", MOPAR_VIN="")
        env.pop("GITHUB_OUTPUT", None)
        for name in ("poll", "send_command", "reset_oil_baseline", "probe_capabilities", "test_connection"):
            with self.subTest(script=name):
                result = subprocess.run(
                    [sys.executable, str(ROOT / "scripts" / (name + ".py")), "lock"],
                    env=env, capture_output=True, text=True, timeout=10,
                )
                self.assertEqual(result.returncode, 1)
                self.assertNotIn("Traceback", result.stdout + result.stderr)
                self.assertIn("MOPAR_", result.stdout + result.stderr)


class AsyncRuntime(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="truck-runtime-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.output = io.StringIO()
        self.enterContext(contextlib.redirect_stdout(self.output))
        self.enterContext(contextlib.redirect_stderr(self.output))
        self.enterContext(patch.dict(os.environ, {
            "MOPAR_EMAIL": "fixture@example.invalid", "MOPAR_PASSWORD": "fixture-password",
            "MOPAR_PIN": "0000", "MOPAR_VIN": VIN,
            "GITHUB_OUTPUT": str(self.root / "github-output"),
        }))
        self.enterContext(patch("urllib.request.urlopen",
                                side_effect=AssertionError("Network access is forbidden in runtime tests")))
        self.enterContext(patch("aiohttp.ClientSession._request", AsyncMock(
            side_effect=AssertionError("Network access is forbidden in runtime tests")
        )))

    def poll_paths(self, module):
        for name, value in {
            "DATA_FILE": self.root / "data.json",
            "LOCATION_FILE": self.root / "location.json",
            "OIL_BASELINE_FILE": self.root / "oil_baseline.json",
            "ALLOWED_VINS": {VIN},
        }.items():
            self.enterContext(patch.object(module, name, value))

    async def test_poll_awaits_endpoints_and_preserves_the_dashboard_contract(self):
        module = load("poll")
        instance = client()
        vehicle = await module.fetch_vehicle(instance, ENTRY)
        row, location, baseline = module.serialize_vehicle(
            vehicle, {VIN: {"odometer_at_last_change_mi": 1000}}, {}
        )
        self.assertEqual(row["year"], "2022")
        self.assertEqual(row["nickname"], "500")
        self.assertEqual(row["odometer_mi"], 5000)
        self.assertEqual(row["range_mi"], 300)
        self.assertEqual(row["fuel_pct"], 67)
        self.assertEqual(row["battery_v"], 12.6)
        self.assertEqual(set(row["tires_psi"].values()), {65})
        self.assertTrue(row["doors_locked"])
        self.assertFalse(row["ignition_on"])
        self.assertEqual(row["oil"]["miles_to_next"], 1000)
        self.assertIsNone(location)
        self.assertNotIn("location", row)
        self.assertNotIn("raw_info", row)
        instance.api.get_vehicle_info.assert_awaited_once_with(VIN, "v4")
        instance.api.get_remote_status.assert_awaited_once_with(VIN)
        instance.api.get_vehicle_location.assert_awaited_once_with(VIN)

    async def test_optional_remote_and_location_failures_keep_core_telemetry(self):
        module = load("poll")
        instance = client()
        instance.api.get_remote_status.side_effect = APIError("fixture unavailable", status=404)
        vehicle = await module.fetch_vehicle(instance, ENTRY)
        row, location, _ = module.serialize_vehicle(vehicle, {}, {})
        self.assertEqual(row["odometer_mi"], 5000)
        self.assertIsNone(row["doors_locked"])
        self.assertIsNone(location)
        self.assertNotIn("fixture unavailable", self.output.getvalue())

    async def test_poll_publishes_only_the_allowlisted_vehicle_and_closes(self):
        module = load("poll")
        self.poll_paths(module)
        instance = client()
        instance.api.list_vehicles.return_value = [dict(ENTRY, vin=OTHER), ENTRY]
        module.OIL_BASELINE_FILE.write_text(json.dumps({
            VIN: {"odometer_at_last_change_mi": 1000},
            OTHER: {"odometer_at_last_change_mi": 999},
        }))
        original_baseline = module.OIL_BASELINE_FILE.read_bytes()
        previous = {"locations": {VIN: {"lat": 0, "lng": 0, "place": "Fixture place"}}}
        module.LOCATION_FILE.write_text(json.dumps(previous))
        with patch.object(module, "Client", return_value=instance):
            await module.async_main()
        data = json.loads(module.DATA_FILE.read_text())
        self.assertEqual([row["vin"] for row in data["vehicles"]], [VIN])
        self.assertEqual(json.loads(module.LOCATION_FILE.read_text())["locations"], previous["locations"])
        self.assertEqual(module.OIL_BASELINE_FILE.read_bytes(), original_baseline)
        instance.api.get_vehicle_info.assert_awaited_once_with(VIN, "v4")
        instance.api.close.assert_awaited_once()

    async def test_failed_required_fetch_keeps_all_last_good_files_and_closes(self):
        module = load("poll")
        self.poll_paths(module)
        files = [module.DATA_FILE, module.LOCATION_FILE, module.OIL_BASELINE_FILE]
        for response in (APIError("fixture-secret-payload", status=502), {}, None, []):
            with self.subTest(response=type(response).__name__):
                for path in files:
                    path.write_text("{}\n")
                before = [path.read_bytes() for path in files]
                instance = client()
                if isinstance(response, Exception):
                    instance.api.get_vehicle_info.side_effect = response
                else:
                    instance.api.get_vehicle_info.return_value = response
                with patch.object(module, "Client", return_value=instance), self.assertRaises(SystemExit) as raised:
                    await module.async_main()
                self.assertEqual(raised.exception.code, 1)
                self.assertEqual([path.read_bytes() for path in files], before)
                instance.api.close.assert_awaited_once()
        self.assertNotIn("fixture-secret-payload", self.output.getvalue())

    async def test_classic_status_version_and_partial_locks_remain_truthful(self):
        module = load("poll")
        instance = client()
        instance.api.get_remote_status.return_value = {
            "doors": {"driver": {"status": "LOCKED"}}
        }
        vehicle = await module.fetch_vehicle(instance, dict(ENTRY, services=[]))
        row, _, _ = module.serialize_vehicle(vehicle, {}, {})
        instance.api.get_vehicle_info.assert_awaited_once_with(VIN, "v3")
        self.assertIsNone(row["doors_locked"])

    async def test_list_failure_is_sanitized_and_closes(self):
        module = load("poll")
        self.poll_paths(module)
        instance = client()
        instance.api.list_vehicles.side_effect = AuthenticationError("fixture-secret-password")
        with patch.object(module, "Client", return_value=instance), self.assertRaises(SystemExit):
            await module.async_main()
        self.assertNotIn("fixture-secret-password", self.output.getvalue())
        self.assertFalse(module.DATA_FILE.exists())
        instance.api.close.assert_awaited_once()

    async def test_command_requires_real_acknowledgement_and_closes(self):
        module = load("send_command")
        for status, expected in (("succeeded", "confirmed"), ("rejected", "rejected")):
            with self.subTest(status=status):
                instance = client()
                instance.api.get_remote_operation_last_status.return_value = {"status": status}
                result_file = self.root / "github-output"
                result_file.unlink(missing_ok=True)
                with patch.object(module, "Client", return_value=instance), patch.object(module, "TARGET_VIN", VIN), patch.object(sys, "argv", ["send_command.py", "lock"]), patch("py_uconnect.client.asyncio.sleep", AsyncMock()):
                    if expected == "confirmed":
                        await module.async_main()
                    else:
                        with self.assertRaises(SystemExit):
                            await module.async_main()
                self.assertEqual(result_file.read_text(), f"result={expected}\n")
                instance.api.command.assert_awaited_once_with(VIN, COMMAND_DOORS_LOCK, None)
                instance.api.close.assert_awaited_once()

    async def test_command_errors_keep_safe_public_result_classes(self):
        module = load("send_command")
        cases = [
            (AuthenticationError("fixture-secret"), "authorization"),
            (PinAuthenticationError("fixture-secret"), "authorization"),
            (APIError("fixture-secret", status=401), "authorization"),
            (APIError("fixture-secret", status=403), "authorization"),
            (APIError("fixture-secret", status=404), "unsupported"),
            (APIError("fixture-secret", status=429), "rate_limited"),
            (APIError("fixture-secret", status=503), "service_unavailable"),
            (CommandTimeoutError("fixture-secret"), "timeout"),
            (CommandError("fixture-secret"), "rejected"),
            (UconnectConnectionError("fixture-secret"), "connection"),
            (TimeoutError("fixture-secret"), "timeout"),
            (ValueError("fixture-secret"), "unexpected"),
        ]
        for error, expected in cases:
            with self.subTest(error=type(error).__name__, result=expected):
                instance = client()
                instance.api.command.side_effect = error
                result_file = self.root / "github-output"
                result_file.unlink(missing_ok=True)
                with patch.object(module, "Client", return_value=instance), patch.object(module, "TARGET_VIN", VIN), patch.object(sys, "argv", ["send_command.py", "lock"]), self.assertRaises(SystemExit):
                    await module.async_main()
                self.assertEqual(result_file.read_text(), f"result={expected}\n")
                instance.api.close.assert_awaited_once()
        self.assertNotIn("fixture-secret", self.output.getvalue())

    async def test_capability_probe_closes_and_never_prints_identity(self):
        module = load("probe_capabilities")
        instance = client()
        instance.api.list_vehicles.return_value = [dict(ENTRY, services=[
            {"service": COMMAND_DOORS_LOCK.name, "vehicleCapable": True, "serviceEnabled": True},
            {"service": "FIXTURE_TELEMETRY", "vehicleCapable": True, "serviceEnabled": True},
        ])]
        with patch.object(module, "Client", return_value=instance):
            await module.async_main()
        data = json.loads(self.output.getvalue())
        self.assertEqual(data["supported_command_codes"], [COMMAND_DOORS_LOCK.name])
        self.assertEqual(data["enabled_non_command_service_codes"], ["FIXTURE_TELEMETRY"])
        self.assertNotIn(VIN, self.output.getvalue())
        self.assertNotIn("fixture@example.invalid", self.output.getvalue())
        instance.api.close.assert_awaited_once()

    async def test_oil_reset_keeps_other_baselines_and_closes(self):
        module = load("reset_oil_baseline")
        instance = client()
        output = self.root / "baseline.json"
        output.write_text(json.dumps({OTHER: {"odometer_at_last_change_mi": 123}}))
        with patch.object(module, "Client", return_value=instance), patch.object(module, "ALLOWED_VINS", {VIN}), patch.object(module, "OIL_BASELINE_FILE", output):
            await module.async_main()
        data = json.loads(output.read_text())
        self.assertEqual(data[OTHER], {"odometer_at_last_change_mi": 123})
        self.assertEqual(data[VIN]["odometer_at_last_change_mi"], 5000)
        self.assertFalse(data[VIN]["auto_anchored"])
        instance.api.close.assert_awaited_once()

    async def test_local_diagnostic_awaits_endpoints_and_closes(self):
        module = load("test_connection")
        instance = client()
        output = self.root / "diagnostic.json"
        with patch.object(module, "Client", return_value=instance), patch.object(module, "OUT", output):
            await module.async_main()
        self.assertEqual(json.loads(output.read_text())[VIN]["status"], INFO)
        instance.api.get_vehicle_info.assert_awaited_once_with(VIN)
        instance.api.close.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
