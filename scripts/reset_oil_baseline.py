"""
reset_oil_baseline.py — Mark current odometer as baseline for oil-change tracking.

NOTE: Your 2022 Ram 2500 reports its OWN oil life percent directly, so this
script is technically optional. The dashboard already shows the real value
from the truck. This baseline is only used as a fallback if the truck ever
stops reporting oilLevel.

Usage (PowerShell):
  $env:MOPAR_EMAIL = "you@example.com"
  $env:MOPAR_PASSWORD = "your_password"
  $env:MOPAR_PIN = "1234"
  python scripts\reset_oil_baseline.py
"""

import json
import os
import sys
from pathlib import Path

import requests
from py_uconnect import Client, brands

ROOT = Path(__file__).parent.parent
OIL_BASELINE_FILE = ROOT / "dashboard" / "oil_baseline.json"

# Same allowlist as poll.py
ALLOWED_VINS = {
    "3C6UR5FJ6NG305274",  # 2022 Ram 2500
}


def to_float(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(str(v).strip())
    except (ValueError, TypeError):
        return None


def km_to_mi(km):
    f = to_float(km)
    return round(f * 0.621371, 1) if f is not None else None


def main() -> None:
    email = os.environ.get("MOPAR_EMAIL")
    password = os.environ.get("MOPAR_PASSWORD")
    pin = os.environ.get("MOPAR_PIN")

    if not (email and password and pin):
        print("ERROR: MOPAR_EMAIL, MOPAR_PASSWORD, MOPAR_PIN must be set")
        sys.exit(1)

    client = Client(email=email, password=password, pin=pin, brand=brands.RAM_US)
    raw_list = client.api.list_vehicles()

    OIL_BASELINE_FILE.parent.mkdir(parents=True, exist_ok=True)
    existing = {}
    if OIL_BASELINE_FILE.exists():
        try:
            existing = json.loads(OIL_BASELINE_FILE.read_text())
        except json.JSONDecodeError:
            existing = {}

    updated = 0
    for entry in raw_list:
        vin = entry["vin"]
        if vin not in ALLOWED_VINS:
            continue

        try:
            info = client.api.get_vehicle(vin)
        except requests.exceptions.HTTPError as e:
            print(f"Skipping {vin}: HTTP {e.response.status_code if e.response else '?'}")
            continue

        try:
            odo_raw = info["vehicleInfo"]["odometer"]["odometer"]
            odo_value = to_float(odo_raw.get("value"))
            odo_unit = (odo_raw.get("unit") or "").lower()
        except (KeyError, TypeError):
            print(f"Skipping {vin}: no odometer data")
            continue

        if odo_value is None:
            print(f"Skipping {vin}: odometer was null")
            continue

        odo_mi = odo_value if odo_unit in ("mi", "miles") else km_to_mi(odo_value)
        existing[vin] = odo_mi
        updated += 1

        try:
            oil_pct = info["vehicleInfo"]["oilLevel"]["oilLevel"]
        except (KeyError, TypeError):
            oil_pct = None

        print(f"  ✓ {entry.get('make')} {entry.get('modelDescription')}: "
              f"baseline = {odo_mi} mi"
              + (f"  (truck reports oil life = {oil_pct}%)" if oil_pct is not None else ""))

    if updated == 0:
        print("No vehicles updated.")
        sys.exit(1)

    OIL_BASELINE_FILE.write_text(json.dumps(existing, indent=2))
    print(f"\nSaved to {OIL_BASELINE_FILE}")
    print("\nCommit and push so GitHub Actions picks it up:")
    print("  git add dashboard/oil_baseline.json")
    print("  git commit -m 'Reset oil change baseline'")
    print("  git push")


if __name__ == "__main__":
    main()
