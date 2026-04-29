"""
poll.py — Fetch Ram data from Stellantis cloud and write data.json.

Runs in GitHub Actions on a schedule. Reads credentials from env vars
(MOPAR_EMAIL, MOPAR_PASSWORD, MOPAR_PIN). Writes dashboard/data.json
which the PWA reads via fetch().

Architecture notes (do not regress):
  * py-uconnect's `client.api.get_vehicle(vin)` returns a raw dict.
    The Vehicle dataclass is populated by passing that dict through
    `_update_vehicle(v, dict)`. We do this manually per VIN so a 502
    on a sibling vehicle (the broken Challenger) doesn't kill the
    whole poll — `client.refresh()` has no per-vehicle try/except.
  * Vehicle attribute names from py-uconnect (NOT obvious):
      - tire pressure: `wheel_front_left_pressure`, etc. (not tire_pressure_*)
      - fuel level pct: `fuel_amount` (not fuel_level_percent)
      - oil life pct: `oil_level` (we ignore this; we use a 5k baseline)

Oil tracking strategy (since 2026-04-29):
  Use a baseline-counter against a 5,000-mile interval. Ignore the truck's
  reported oilLevel. Baseline auto-populates on first run for any new VIN,
  then only changes when the user re-anchors after an oil change.
"""

import json
import os
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

from py_uconnect import Client, brands
from py_uconnect.client import Vehicle, Location, _update_vehicle

ROOT = Path(__file__).parent.parent
DATA_FILE = ROOT / "dashboard" / "data.json"
OIL_BASELINE_FILE = ROOT / "dashboard" / "oil_baseline.json"
OIL_CHANGE_INTERVAL_MILES = 5000

# VIN allowlist — only these vehicles get fetched and rendered.
ALLOWED_VINS = {
    "3C6UR5FJ6NG305274",  # 2022 Ram 2500
}


# ─── Number coercion helpers ────────────────────────────────────────────────
def to_float(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        s = v.strip().lower()
        if s in ("", "null", "none", "n/a"):
            return None
        try:
            return float(s)
        except ValueError:
            return None
    return None


def to_int(v):
    f = to_float(v)
    return int(f) if f is not None else None


def km_to_mi(km):
    f = to_float(km)
    return round(f * 0.621371, 1) if f is not None else None


def kpa_to_psi(kpa):
    f = to_float(kpa)
    return round(f * 0.145038, 1) if f is not None else None


def normalize_distance(value, unit):
    f = to_float(value)
    if f is None:
        return None
    u = (unit or "").lower()
    if u in ("mi", "miles"):
        return round(f, 1)
    return km_to_mi(f)


def normalize_pressure(value, unit):
    f = to_float(value)
    if f is None:
        return None
    u = (unit or "").lower()
    if u == "psi":
        return round(f, 1)
    return kpa_to_psi(f)


# ─── Oil baseline ──────────────────────────────────────────────────────────
def load_oil_baseline() -> dict:
    if OIL_BASELINE_FILE.exists():
        try:
            return json.loads(OIL_BASELINE_FILE.read_text())
        except json.JSONDecodeError:
            return {}
    return {}


def save_oil_baseline(baseline: dict) -> None:
    OIL_BASELINE_FILE.parent.mkdir(parents=True, exist_ok=True)
    OIL_BASELINE_FILE.write_text(json.dumps(baseline, indent=2))


def compute_oil(vin: str, odometer_mi, baseline: dict):
    if odometer_mi is None:
        return ({
            "interval_mi": OIL_CHANGE_INTERVAL_MILES,
            "baseline_mi": None,
            "miles_since": None,
            "miles_to_next": None,
        }, baseline)

    entry = baseline.get(vin)
    # Tolerate both the legacy bare-number form and the structured form.
    if isinstance(entry, (int, float)):
        entry = {"odometer_at_last_change_mi": entry}
    if not entry or "odometer_at_last_change_mi" not in entry:
        baseline[vin] = {
            "odometer_at_last_change_mi": round(odometer_mi),
            "set_at": datetime.now(timezone.utc).isoformat(),
            "auto_anchored": True,
        }
        entry = baseline[vin]

    base_odo = entry["odometer_at_last_change_mi"]
    miles_since = max(0, round(odometer_mi - base_odo))
    miles_to_next = OIL_CHANGE_INTERVAL_MILES - miles_since

    return ({
        "interval_mi": OIL_CHANGE_INTERVAL_MILES,
        "baseline_mi": base_odo,
        "miles_since": miles_since,
        "miles_to_next": miles_to_next,
        "baseline_set_at": entry.get("set_at"),
        "auto_anchored": entry.get("auto_anchored", False),
    }, baseline)


# ─── Resilient per-vehicle fetch ───────────────────────────────────────────
def fetch_vehicle(client, vin_entry: dict) -> Vehicle:
    """Build a populated Vehicle for a single VIN without using
    client.refresh() (which crashes on the broken Challenger)."""
    vin = vin_entry["vin"]

    vehicle = Vehicle(
        vin=vin,
        nickname=vin_entry.get("nickname") or "",
        make=vin_entry.get("make") or "",
        model=vin_entry.get("modelDescription") or "",
        year=str(vin_entry.get("year") or vin_entry.get("tsoModelYear") or ""),
        region=vin_entry.get("soldRegion") or "",
    )
    vehicle.sdp = vin_entry.get("sdp")
    vehicle.image_url = vin_entry.get("vehicleImageURL")
    vehicle.fuel_type = vin_entry.get("fuelType")

    info = client.api.get_vehicle(vin)
    _update_vehicle(vehicle, info)

    # Location is a separate API call; tolerate failure.
    try:
        loc = client.api.get_vehicle_location(vin)
        updated = (
            datetime.fromtimestamp(loc["timeStamp"] / 1000).astimezone()
            if "timeStamp" in loc
            else None
        )
        vehicle.location = Location(
            longitude=loc.get("longitude"),
            latitude=loc.get("latitude"),
            altitude=loc.get("altitude"),
            bearing=loc.get("bearing"),
            is_approximate=loc.get("isLocationApprox"),
            updated=updated,
        )
    except Exception:
        pass

    return vehicle


# ─── Per-vehicle serializer ────────────────────────────────────────────────
def serialize_vehicle(v: Vehicle, oil_baseline: dict):
    odometer_mi = normalize_distance(v.odometer, v.odometer_unit)
    range_mi = normalize_distance(v.distance_to_empty, v.distance_to_empty_unit)

    tires_psi = {
        "front_left":  normalize_pressure(v.wheel_front_left_pressure,  v.wheel_front_left_pressure_unit),
        "front_right": normalize_pressure(v.wheel_front_right_pressure, v.wheel_front_right_pressure_unit),
        "rear_left":   normalize_pressure(v.wheel_rear_left_pressure,   v.wheel_rear_left_pressure_unit),
        "rear_right":  normalize_pressure(v.wheel_rear_right_pressure,  v.wheel_rear_right_pressure_unit),
    }
    tires_warning = {
        "front_left":  bool(v.wheel_front_left_pressure_warning)  if v.wheel_front_left_pressure_warning  is not None else False,
        "front_right": bool(v.wheel_front_right_pressure_warning) if v.wheel_front_right_pressure_warning is not None else False,
        "rear_left":   bool(v.wheel_rear_left_pressure_warning)   if v.wheel_rear_left_pressure_warning   is not None else False,
        "rear_right":  bool(v.wheel_rear_right_pressure_warning)  if v.wheel_rear_right_pressure_warning  is not None else False,
    }

    location = None
    if v.location:
        location = {
            "lat": to_float(v.location.latitude),
            "lng": to_float(v.location.longitude),
            "ts": str(v.location.updated) if v.location.updated else None,
            "place": None,
        }

    oil_block, oil_baseline = compute_oil(v.vin, odometer_mi, oil_baseline)

    return ({
        "vin": v.vin,
        "year": v.year or None,
        "make": v.make or None,
        "model": v.model or None,
        "nickname": v.nickname or None,
        "odometer_mi": odometer_mi,
        "range_mi": range_mi,
        "fuel_pct": to_int(v.fuel_amount),
        "fuel_low": bool(v.fuel_low) if v.fuel_low is not None else False,
        "battery_v": to_float(v.battery_voltage),
        "tires_psi": tires_psi,
        "tires_warning": tires_warning,
        "location": location,
        "oil": oil_block,
    }, oil_baseline)


# ─── Main ──────────────────────────────────────────────────────────────────
def main() -> None:
    email = os.environ.get("MOPAR_EMAIL")
    password = os.environ.get("MOPAR_PASSWORD")
    pin = os.environ.get("MOPAR_PIN")

    if not (email and password and pin):
        print("ERROR: MOPAR_EMAIL, MOPAR_PASSWORD, MOPAR_PIN must be set", file=sys.stderr)
        sys.exit(1)

    client = Client(email=email, password=password, pin=pin, brand=brands.RAM_US)

    try:
        listed = client.api.list_vehicles()
    except Exception as e:
        print(f"ERROR listing vehicles: {e}", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)

    oil_baseline = load_oil_baseline()
    vehicles_out = []

    for entry in listed:
        vin = entry.get("vin")
        if not vin:
            continue
        if vin not in ALLOWED_VINS:
            print(f"  · {vin} — skipped (not in allowlist)")
            continue

        try:
            vehicle = fetch_vehicle(client, entry)
            vd, oil_baseline = serialize_vehicle(vehicle, oil_baseline)
            vehicles_out.append(vd)
            mtn = (vd.get("oil") or {}).get("miles_to_next")
            print(f"  ✓ {vin}: odo={vd.get('odometer_mi')} mi · oil_to_next={mtn} mi")
        except Exception as e:
            print(f"  ! {vin}: fetch failed — {type(e).__name__}: {e}", file=sys.stderr)
            traceback.print_exc()

    if not vehicles_out:
        print("No vehicles fetched successfully — leaving data.json untouched", file=sys.stderr)
        sys.exit(1)

    output = {
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "vehicles": vehicles_out,
    }

    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(json.dumps(output, indent=2, default=str))
    save_oil_baseline(oil_baseline)
    print(f"Wrote {DATA_FILE}")


if __name__ == "__main__":
    main()
