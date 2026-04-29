"""
poll.py v2 — Fetch Ram data from Stellantis cloud and write data.json.

Resilient version. Uses py-uconnect's lower-level api directly so one bad
vehicle (e.g. the Challenger that 502s) doesn't crash the entire poll.

Reads credentials from env vars: MOPAR_EMAIL, MOPAR_PASSWORD, MOPAR_PIN.
Writes dashboard/data.json which the PWA reads.

Filters by VIN allowlist — only your Ram is processed; the Challenger and
any future-added vehicles are ignored unless explicitly added below.
"""

import json
import os
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

import requests
from py_uconnect import Client, brands

ROOT = Path(__file__).parent.parent
DATA_FILE = ROOT / "dashboard" / "data.json"
OIL_BASELINE_FILE = ROOT / "dashboard" / "oil_baseline.json"
OIL_CHANGE_INTERVAL_MILES = 5000

# VIN allowlist — only these vehicles get fetched and rendered.
# Add more VINs here if you want to include additional vehicles.
ALLOWED_VINS = {
    "3C6UR5FJ6NG305274",  # 2022 Ram 2500
}


# ─── Number coercion helpers ────────────────────────────────────────────────
# py-uconnect returns API values as strings (sometimes literally "null")
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
    """Convert a distance to miles. Returns float or None."""
    f = to_float(value)
    if f is None:
        return None
    u = (unit or "").lower()
    if u in ("mi", "miles"):
        return round(f, 1)
    return km_to_mi(f)


def normalize_pressure(value, unit):
    """Convert a tire pressure to PSI. Returns float or None."""
    f = to_float(value)
    if f is None:
        return None
    u = (unit or "").lower()
    if u == "psi":
        return round(f, 1)
    return kpa_to_psi(f)


# ─── Oil baseline (used as fallback if vehicle doesn't report oil life %) ──
def load_oil_baseline() -> dict:
    if OIL_BASELINE_FILE.exists():
        try:
            return json.loads(OIL_BASELINE_FILE.read_text())
        except json.JSONDecodeError:
            return {}
    return {}


# ─── Per-vehicle serializer ────────────────────────────────────────────────
def serialize_vehicle(v, oil_baseline: dict) -> dict:
    """Convert a py-uconnect Vehicle dataclass to dashboard JSON shape."""
    odometer_mi = normalize_distance(v.odometer, v.odometer_unit)
    range_mi = normalize_distance(v.distance_to_empty, v.distance_to_empty_unit)
    dts_mi = normalize_distance(v.distance_to_service, v.distance_to_service_unit)

    # Oil life — prefer real value reported by the truck; fall back to baseline.
    reported_oil_pct = to_int(v.oil_level)

    oil_change = None
    if reported_oil_pct is not None:
        oil_change = {
            "source": "vehicle",
            "oil_life_percent": reported_oil_pct,
        }
    elif odometer_mi is not None and v.vin in oil_baseline:
        baseline = oil_baseline[v.vin]
        miles_since = odometer_mi - baseline
        miles_until = OIL_CHANGE_INTERVAL_MILES - miles_since
        life_pct = max(0, min(100, round((miles_until / OIL_CHANGE_INTERVAL_MILES) * 100, 1)))
        oil_change = {
            "source": "baseline",
            "baseline_miles": baseline,
            "miles_since_change": round(miles_since, 1),
            "miles_until_due": round(miles_until, 1),
            "oil_life_percent": life_pct,
            "interval_miles": OIL_CHANGE_INTERVAL_MILES,
        }

    return {
        "vin": v.vin,
        "nickname": v.nickname or None,
        "year": v.year,
        "make": v.make,
        "model": v.model,
        "odometer_miles": odometer_mi,
        "range_miles": range_mi,
        "distance_to_service_miles": dts_mi,
        "days_to_service": v.days_to_service,
        "fuel_low": v.fuel_low,
        "fuel_level_percent": to_int(v.fuel_amount),
        "battery_voltage": to_float(v.battery_voltage),
        "ignition_on": v.ignition_on,
        "trunk_locked": v.trunk_locked,
        "doors": {
            "driver_locked": v.door_driver_locked,
            "passenger_locked": v.door_passenger_locked,
            "rear_left_locked": v.door_rear_left_locked,
            "rear_right_locked": v.door_rear_right_locked,
        },
        "windows": {
            "driver_closed": v.window_driver_closed,
            "passenger_closed": v.window_passenger_closed,
        },
        "tires_psi": {
            "front_left": normalize_pressure(v.wheel_front_left_pressure, v.wheel_front_left_pressure_unit),
            "front_right": normalize_pressure(v.wheel_front_right_pressure, v.wheel_front_right_pressure_unit),
            "rear_left": normalize_pressure(v.wheel_rear_left_pressure, v.wheel_rear_left_pressure_unit),
            "rear_right": normalize_pressure(v.wheel_rear_right_pressure, v.wheel_rear_right_pressure_unit),
        },
        "tire_warnings": {
            "front_left": v.wheel_front_left_pressure_warning,
            "front_right": v.wheel_front_right_pressure_warning,
            "rear_left": v.wheel_rear_left_pressure_warning,
            "rear_right": v.wheel_rear_right_pressure_warning,
        },
        "location": {
            "latitude": v.location.latitude,
            "longitude": v.location.longitude,
            "updated": str(v.location.updated) if v.location.updated else None,
        } if v.location else None,
        "oil_change": oil_change,
        "supported_commands": v.supported_commands,
    }


# ─── Resilient per-vehicle fetch ───────────────────────────────────────────
def fetch_vehicle_resilient(client, vin_entry):
    """Build a Vehicle dataclass for a single VIN. Bypasses client.refresh()
    so a 502 on a sibling vehicle doesn't kill the whole call.
    """
    from py_uconnect.client import Vehicle, _update_vehicle, Location
    from datetime import datetime as _dt

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

    # Main status fetch
    info = client.api.get_vehicle(vin)
    _update_vehicle(vehicle, info)

    # Location (best-effort)
    try:
        loc_data = client.api.get_vehicle_location(vin)
        updated = (
            _dt.fromtimestamp(loc_data["timeStamp"] / 1000).astimezone()
            if "timeStamp" in loc_data
            else None
        )
        vehicle.location = Location(
            longitude=loc_data.get("longitude"),
            latitude=loc_data.get("latitude"),
            altitude=loc_data.get("altitude"),
            bearing=loc_data.get("bearing"),
            is_approximate=loc_data.get("isLocationApprox"),
            updated=updated,
        )
    except Exception:
        pass

    return vehicle


def main() -> None:
    email = os.environ.get("MOPAR_EMAIL")
    password = os.environ.get("MOPAR_PASSWORD")
    pin = os.environ.get("MOPAR_PIN")

    if not (email and password and pin):
        print("ERROR: MOPAR_EMAIL, MOPAR_PASSWORD, MOPAR_PIN must be set", file=sys.stderr)
        sys.exit(1)

    started = datetime.now(timezone.utc)
    print(f"[{started.isoformat()}] Polling Stellantis cloud…")

    client = Client(email=email, password=password, pin=pin, brand=brands.RAM_US)

    try:
        raw_list = client.api.list_vehicles()
    except Exception as e:
        print(f"ERROR: failed to list vehicles: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Account has {len(raw_list)} vehicle(s); allowlist: {ALLOWED_VINS}")

    oil_baseline = load_oil_baseline()
    serialized = []
    errors = []

    for entry in raw_list:
        vin = entry.get("vin", "?")
        if vin not in ALLOWED_VINS:
            print(f"  - SKIP {vin} (not in allowlist)")
            continue

        try:
            vehicle = fetch_vehicle_resilient(client, entry)
            data = serialize_vehicle(vehicle, oil_baseline)
            serialized.append(data)
            oil_disp = (data['oil_change']['oil_life_percent']
                        if data['oil_change'] else 'n/a')
            print(f"  ✓ {vin}: odo={data['odometer_miles']} mi, "
                  f"range={data['range_miles']} mi, oil_life={oil_disp}%")
        except requests.exceptions.HTTPError as e:
            code = e.response.status_code if e.response is not None else "?"
            err = f"HTTP {code}"
            print(f"  ✗ {vin}: {err}", file=sys.stderr)
            errors.append({"vin": vin, "error": err})
        except Exception as e:
            err = f"{type(e).__name__}: {e}"
            print(f"  ✗ {vin}: {err}", file=sys.stderr)
            traceback.print_exc()
            errors.append({"vin": vin, "error": err})

    if not serialized:
        print("ERROR: no vehicles returned successfully — leaving data.json untouched",
              file=sys.stderr)
        sys.exit(1)

    out = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "vehicles": serialized,
        "errors": errors,
    }

    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(json.dumps(out, indent=2, default=str))
    print(f"Wrote {DATA_FILE}")


if __name__ == "__main__":
    main()
