r"""
send_command.py — Send remote commands to the Ram (lock, unlock, start, etc).

Uses client.command_verify(), which waits (up to ~60 s) for the vehicle to
acknowledge the command. In GitHub Actions it also emits one allowlisted result
class through GITHUB_OUTPUT so the dashboard can distinguish a vehicle
rejection from a timeout, authorization problem, or service outage without
publishing raw Stellantis responses.

Commands wired to the dashboard buttons + command.yml:
  lock, unlock, engine_on, engine_off, lights, lights_horn,
  refresh_location, deep_refresh

CLI-only extras (no power trunk on this truck; kept for experiments):
  trunk_lock, trunk_unlock

Usage (PowerShell):
  $env:MOPAR_EMAIL = "you@example.com"
  $env:MOPAR_PASSWORD = "your_password"
  $env:MOPAR_PIN = "1234"
  python scripts\send_command.py lock
"""

import os
import sys

from py_uconnect import Client, brands
from py_uconnect.command import (
    COMMAND_DEEP_REFRESH,
    COMMAND_DOORS_LOCK,
    COMMAND_DOORS_UNLOCK,
    COMMAND_ENGINE_ON,
    COMMAND_ENGINE_OFF,
    COMMAND_LIGHTS,
    COMMAND_LIGHTS_HORN,
    COMMAND_REFRESH_LOCATION,
    COMMAND_TRUNK_LOCK,
    COMMAND_TRUNK_UNLOCK,
)
from requests.exceptions import HTTPError, RequestException, Timeout

# Hardcoded — your Ram only. Edit if you want to send commands to a different vehicle.
TARGET_VIN = "3C6UR5FJ6NG305274"

CMD_MAP = {
    "lock": COMMAND_DOORS_LOCK,
    "unlock": COMMAND_DOORS_UNLOCK,
    "engine_on": COMMAND_ENGINE_ON,
    "engine_off": COMMAND_ENGINE_OFF,
    "lights": COMMAND_LIGHTS,
    "lights_horn": COMMAND_LIGHTS_HORN,
    "refresh_location": COMMAND_REFRESH_LOCATION,
    "deep_refresh": COMMAND_DEEP_REFRESH,
    "trunk_lock": COMMAND_TRUNK_LOCK,
    "trunk_unlock": COMMAND_TRUNK_UNLOCK,
}

RESULTS = {
    "confirmed",
    "rejected",
    "timeout",
    "authorization",
    "unsupported",
    "rate_limited",
    "service_unavailable",
    "connection",
    "configuration",
    "unexpected",
}


def emit_result(result: str) -> None:
    """Publish only a safe, allowlisted result class."""
    if result not in RESULTS:
        result = "unexpected"
    print(f"TRUCK_APP_RESULT={result}")
    output_path = os.environ.get("GITHUB_OUTPUT")
    if output_path:
        with open(output_path, "a", encoding="utf-8") as output:
            output.write(f"result={result}\n")


def classify_exception(exc: Exception) -> str:
    """Map exceptions to public-safe categories without exposing API payloads."""
    if isinstance(exc, (Timeout, TimeoutError)):
        return "timeout"

    if isinstance(exc, HTTPError):
        response = getattr(exc, "response", None)
        status = getattr(response, "status_code", None)
        if status in {401, 403}:
            return "authorization"
        if status == 404:
            return "unsupported"
        if status == 429:
            return "rate_limited"
        if isinstance(status, int) and status >= 500:
            return "service_unavailable"
        return "unexpected"

    if isinstance(exc, RequestException):
        return "connection"

    message = str(exc).lower()
    if "timed out" in message or "timeout" in message:
        return "timeout"
    if "authenticate" in message or "unauthorized" in message:
        return "authorization"
    return "unexpected"


def fail(result: str, message: str) -> None:
    emit_result(result)
    print(message)
    raise SystemExit(1)


def main() -> None:
    if len(sys.argv) < 2:
        print(f"Usage: python {sys.argv[0]} <command>")
        print(f"Available: {', '.join(CMD_MAP.keys())}")
        fail("configuration", "Command name is required.")

    cmd_name = sys.argv[1].lower()
    if cmd_name not in CMD_MAP:
        print(f"Unknown command: {cmd_name}")
        print(f"Available: {', '.join(CMD_MAP.keys())}")
        fail("configuration", "Command name is not supported by this app.")

    email = os.environ.get("MOPAR_EMAIL")
    password = os.environ.get("MOPAR_PASSWORD")
    pin = os.environ.get("MOPAR_PIN")

    if not (email and password and pin):
        fail(
            "configuration",
            "MOPAR_EMAIL, MOPAR_PASSWORD, and MOPAR_PIN must be configured.",
        )

    try:
        client = Client(
            email=email,
            password=password,
            pin=pin,
            brand=brands.RAM_US,
        )
        cmd = CMD_MAP[cmd_name]
        print(
            f"Sending {cmd.name} to the configured Ram and waiting "
            "for the vehicle to acknowledge it…"
        )
        ok = client.command_verify(TARGET_VIN, cmd)
    except Exception as exc:
        result = classify_exception(exc)
        status = getattr(getattr(exc, "response", None), "status_code", None)
        detail = f" (HTTP {status})" if isinstance(status, int) else ""
        fail(
            result,
            f"Command could not be completed: {type(exc).__name__}{detail}.",
        )

    if ok:
        emit_result("confirmed")
        print("Command confirmed by the vehicle.")
    else:
        fail(
            "rejected",
            "The vehicle rejected the command or it was not applicable "
            "in its current state.",
        )


if __name__ == "__main__":
    main()
