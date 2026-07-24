r"""
probe_capabilities.py — Read the Ram account's advertised service capabilities.

This diagnostic performs one read-only list_vehicles call. Its output is
deliberately limited to service codes: it does not print the VIN, vehicle
identity, location, subscription dates, credentials, or raw API payloads, and
it does not write any files.

Usage (PowerShell):
  $env:MOPAR_EMAIL = "you@example.com"
  $env:MOPAR_PASSWORD = "your_password"
  $env:MOPAR_PIN = "1234"
  $env:MOPAR_VIN = "your_vehicle_vin"
  python scripts\probe_capabilities.py
"""

import json
import os
import sys
from typing import Any

from py_uconnect import Client, brands
from py_uconnect.command import COMMANDS_BY_NAME


def is_enabled(value: Any) -> bool:
    """Accept the boolean and string forms seen in Stellantis payloads."""
    return value is True or (
        isinstance(value, str) and value.strip().lower() == "true"
    )


def summarize_vehicle_entry(entry: dict[str, Any]) -> dict[str, Any]:
    """Return only allowlisted capability information from a vehicle entry."""
    enabled = set()
    for service in entry.get("services") or []:
        if not isinstance(service, dict):
            continue
        code = service.get("service")
        if (
            isinstance(code, str)
            and code
            and is_enabled(service.get("vehicleCapable"))
            and is_enabled(service.get("serviceEnabled"))
        ):
            enabled.add(code)

    commands = sorted(enabled.intersection(COMMANDS_BY_NAME))
    non_commands = sorted(enabled.difference(COMMANDS_BY_NAME))
    return {
        "vehicle_found": True,
        "supported_command_codes": commands,
        "enabled_non_command_service_codes": non_commands,
    }


def main() -> None:
    email = os.environ.get("MOPAR_EMAIL")
    password = os.environ.get("MOPAR_PASSWORD")
    pin = os.environ.get("MOPAR_PIN")
    target_vin = os.environ.get("MOPAR_VIN")
    if not (email and password and pin and target_vin):
        print(
            "ERROR: MOPAR_EMAIL, MOPAR_PASSWORD, MOPAR_PIN, and MOPAR_VIN "
            "must be set",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        client = Client(
            email=email,
            password=password,
            pin=pin,
            brand=brands.RAM_US,
        )
        vehicles = client.api.list_vehicles()
    except Exception as exc:
        # Public logs must never receive raw API errors, URLs, or payloads.
        print(
            f"ERROR: capability lookup failed ({type(exc).__name__})",
            file=sys.stderr,
        )
        sys.exit(1)

    entry = next(
        (
            item
            for item in vehicles
            if isinstance(item, dict) and item.get("vin") == target_vin
        ),
        None,
    )
    if entry is None:
        print(json.dumps({"vehicle_found": False}, indent=2))
        sys.exit(2)

    print(json.dumps(summarize_vehicle_entry(entry), indent=2))


if __name__ == "__main__":
    main()
