"""
test_connection.py v2 — Resilient diagnostic.

Same purpose as before: verify Mopar credentials work and dump everything
the API returns. But this version handles per-vehicle errors gracefully
so one broken vehicle (asleep modem, 502, expired subscription) doesn't
prevent the others from being read.

Usage (PowerShell):
  $env:MOPAR_EMAIL = "you@example.com"
  $env:MOPAR_PASSWORD = "your_password"
  $env:MOPAR_PIN = "1234"
  python scripts\test_connection.py
"""

import json
import os
import sys
import traceback
from pathlib import Path

import requests
from py_uconnect import Client, brands

OUT = Path(__file__).parent.parent / "test_output.json"


def main() -> None:
    email = os.environ.get("MOPAR_EMAIL")
    password = os.environ.get("MOPAR_PASSWORD")
    pin = os.environ.get("MOPAR_PIN")

    if not (email and password and pin):
        print("ERROR: set MOPAR_EMAIL, MOPAR_PASSWORD, MOPAR_PIN env vars")
        sys.exit(1)

    print(f"Logging in as {email}…")
    client = Client(email=email, password=password, pin=pin, brand=brands.RAM_US)

    # Bypass client.refresh() because it bails on the first vehicle that errors.
    # Use the lower-level api directly so we can per-vehicle try/except.
    print("Listing vehicles on account…")
    try:
        raw_list = client.api.list_vehicles()
    except Exception as e:
        print(f"ERROR listing vehicles: {e}")
        sys.exit(1)

    print(f"\nAccount has {len(raw_list)} vehicle(s):\n")

    raw_dump = {}
    successes = 0
    failures = 0

    for entry in raw_list:
        vin = entry.get("vin", "?")
        nick = entry.get("nickname", "?")
        make = entry.get("make", "?")
        model = entry.get("modelDescription", "?")
        year = entry.get("tsoModelYear", "?")
        sdp = entry.get("sdp", "?")

        print(f"━━━ {year} {make} {model} ({nick}) ━━━")
        print(f"   VIN: {vin}")
        print(f"   SDP: {sdp}  (Uconnect/SXM Guardian indicator)")

        v_dump = {
            "vin": vin,
            "nickname": nick,
            "make": make,
            "model": model,
            "year": year,
            "sdp": sdp,
            "list_entry": entry,
        }

        # Try fetching status
        try:
            status = client.api.get_vehicle(vin)
            v_dump["status"] = status
            print(f"   ✓ Status fetch OK")

            # Pull a few interesting fields out for quick visual check
            vi = status.get("vehicleInfo", {}) if isinstance(status, dict) else {}
            odo = vi.get("odometer", {}).get("odometer", {}).get("value")
            odo_unit = vi.get("odometer", {}).get("odometer", {}).get("unit")
            if odo is not None:
                print(f"   Odometer: {odo} {odo_unit}")

            successes += 1
        except requests.exceptions.HTTPError as e:
            code = e.response.status_code if e.response is not None else "?"
            print(f"   ✗ Status fetch failed: HTTP {code}")
            v_dump["status_error"] = f"HTTP {code}: {str(e)}"
            failures += 1
        except Exception as e:
            print(f"   ✗ Status fetch failed: {type(e).__name__}: {e}")
            v_dump["status_error"] = f"{type(e).__name__}: {e}"
            failures += 1

        # Try fetching location (optional)
        try:
            loc = client.api.get_vehicle_location(vin)
            v_dump["location"] = loc
            lat = loc.get("latitude")
            lon = loc.get("longitude")
            if lat and lon:
                print(f"   Location: {lat}, {lon}")
        except Exception as e:
            print(f"   (no location: {type(e).__name__})")

        raw_dump[vin] = v_dump
        print()

    print("━" * 50)
    print(f"Summary: {successes} succeeded, {failures} failed")
    print(f"Full raw output saved to: {OUT}")

    OUT.write_text(json.dumps(raw_dump, indent=2, default=str))

    if successes == 0:
        print("\n⚠ No vehicles returned data. The Stellantis API may be temporarily")
        print("  down — wait 15 min and try again. Check brandreliability.smartcar.com")
        sys.exit(1)


if __name__ == "__main__":
    main()
