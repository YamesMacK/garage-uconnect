"""
poll.py — Fetch Ram data from Stellantis cloud and write data.json.

Runs in GitHub Actions on a schedule. Reads credentials from env vars
(MOPAR_EMAIL, MOPAR_PASSWORD, MOPAR_PIN). Writes dashboard/data.json
which the PWA reads via fetch().

Oil tracking strategy (since 2026-04-29):
  Always use a baseline-counter against a 5,000-mile interval.
  Ignore the truck's reported oil-life percentage entirely.
  Baseline is auto-populated on first run for any new VIN, then only
  changes when the user hits "Reset" after an oil change.
"""

import json
import os
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

from py_uconnect import Client, brands

ROOT = Path(__file__).parent.parent
DATA_FILE = ROOT / "dashboard" / "data.json"
OIL_BASELINE_FILE = ROOT / "dashboard" / "oil_baseline.json"
OIL_CHANGE_INTERVAL_MILES = 5000

# VIN allowlist — only these vehicles get fetched and rendered.
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


def compute_oil(vin: str, odometer_mi, baseline: dict) -> tuple[dict, dict]:
    """
    Return (oil_block_for_data_json, possibly_updated_baseline_dict).

    If this VIN has no baseline yet, anchor it to the current odometer so the
    dashboard shows a full 5,000 mi until next change. James can hit Reset
    after his next oil change to re-anchor to truth.
    """
    if odometer_mi is None:
        return ({
            "interval_mi": OIL_CHANGE_INTERVAL_MILES,
            "baseline_mi": None,
            "miles_since": None,
            "miles_to_next": None,
        }, baseline)

    entry = baseline.get(vin)
    if not entry or "odometer_at_last_change_mi" not in entry:
        # First-run anchor
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


# ─── Per-vehicle serializer ────────────────────────────────────────────────
def serialize_vehicle(v, oil_baseline: dict) -> tuple[dict, dict]:
    """Convert a py-uconnect Vehicle to dashboard JSON shape.
    Returns (vehicle_dict, updated_oil_baseline)."""
    odometer_mi = normalize_distance(v.odometer, v.odometer_unit)
    range_mi = normalize_distance(v.distance_to_empty, v.distance_to_empty_unit)

    # Tires — kPa → PSI
    tires_psi = {}
    tires_warn = {}
    for corner in ("front_left", "front_right", "rear_left", "rear_right"):
        pressure_attr = f"tire_pressure_{corner}"
        unit_attr = f"tire_pressure_{corner}_unit"
        warn_attr = f"tire_pressure_{corner}_warning"
        tires_psi[corner] = normalize_pressure(
            getattr(v, pressure_attr, None),
            getattr(v, unit_attr, None),
        )
        warn_val = getattr(v, warn_attr, None)
        tires_warn[corner] = bool(warn_val) if warn_val is not None else False

    # Location
    location = None
    if v.location:
        location = {
            "lat": to_float(v.location.latitude),
            "lng": to_float(v.location.longitude),
            "ts": getattr(v.location, "timestamp", None),
        }
        # Best-effort label (poll.py doesn't reverse-geocode; the dashboard
        # falls back to coords if `place` is missing).
        location["place"] = None

    # Oil 5k tracker
    oil_block, oil_baseline = compute_oil(v.vin, odometer_mi, oil_baseline)

    return ({
        "vin": v.vin,
        "year": getattr(v, "year", None),
        "make": getattr(v, "make", None),
        "model": getattr(v, "model", None),
        "nickname": getattr(v, "nickname", None) or "Garage",
        "odometer_mi": odometer_mi,
        "range_mi": range_mi,
        "fuel_pct": to_int(getattr(v, "fuel_level_percent", None)),
        "fuel_low": bool(getattr(v, "fuel_low_warning", False)),
        "battery_v": to_float(getattr(v, "battery_voltage", None)),
        "tires_psi": tires_psi,
        "tires_warning": tires_warn,
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

    # Lower-level API access avoids client.refresh() which has no per-vehicle
    # try/except and crashes on the broken Challenger 502.
    try:
        listed = client.api.list_vehicles()
    except Exception as e:
        print(f"ERROR listing vehicles: {e}", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)

    oil_baseline = load_oil_baseline()
    vehicles_out = []

    for vehicle_summary in listed:
        vin = getattr(vehicle_summary, "vin", None) or vehicle_summary.get("vin")
        if not vin:
            continue
        if vin not in ALLOWED_VINS:
            print(f"  · {vin} — skipped (not in allowlist)")
            continue

        try:
            v = client.api.get_vehicle(vin)
            vd, oil_baseline = serialize_vehicle(v, oil_baseline)
            vehicles_out.append(vd)
            odo = vd.get("odometer_mi")
            mtn = (vd.get("oil") or {}).get("miles_to_next")
            print(f"  ✓ {vin}: odo={odo} mi · oil_to_next={mtn} mi")
        except Exception as e:
            print(f"  ! {vin}: fetch failed — {e}", file=sys.stderr)

    if not vehicles_out:
        print("No vehicles fetched successfully — leaving data.json untouched", file=sys.stderr)
        sys.exit(1)

    output = {
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "vehicles": vehicles_out,
    }

    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(json.dumps(output, indent=2))
    save_oil_baseline(oil_baseline)
    print(f"Wrote {DATA_FILE}")


if __name__ == "__main__":
    main()
