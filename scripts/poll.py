"""
poll.py — Fetch Ram data from Stellantis cloud and write data.json + location.json.

Runs in GitHub Actions on a schedule. Reads credentials from env vars
(MOPAR_EMAIL, MOPAR_PASSWORD, MOPAR_PIN). Writes dashboard/data.json
(committed to git) and dashboard/location.json (NOT committed — deployed
to Pages via the workflow artifact only, so GPS history never lands in
public git history; see poll.yml).

Architecture notes (do not regress):
  * py-uconnect's `client.api.get_vehicle(vin)` returns a raw dict.
    The Vehicle dataclass is populated by passing that dict through
    `_update_vehicle(v, dict)`. We do this manually per VIN so a bad
    sibling vehicle (the broken Challenger) doesn't kill the whole
    poll — `client.refresh()` also makes extra per-vehicle calls we
    don't need every 30 minutes.
  * Since py-uconnect 0.4.x, get_vehicle() returns {} on HTTP
    400/404/502 instead of raising. An empty dict must be treated as
    a failed fetch or the poll would silently write an all-null row.
  * Door lock / window / engine state come from a SEPARATE endpoint
    (get_vehicle_status). It's called best-effort: subscriptions
    without that data just leave the fields null.
  * Vehicle attribute names from py-uconnect (NOT obvious):
      - tire pressure: `wheel_front_left_pressure`, etc. (not tire_pressure_*)
      - fuel level pct: `fuel_amount` (not fuel_level_percent)
      - oil life pct: `oil_level` (informational only; we use a 5k baseline)

Oil tracking strategy (since 2026-04-29):
  Use a baseline-counter against a 5,000-mile interval. Ignore the truck's
  reported oilLevel for the DUE calculation (it is surfaced as a secondary
  readout only). Baseline auto-populates on first run for any new VIN,
  then only changes when the user re-anchors after an oil change.
"""

import json
import os
import sys
import urllib.request
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

from py_uconnect import Client, brands
from py_uconnect.client import Vehicle, Location, _update_vehicle

ROOT = Path(__file__).parent.parent
DATA_FILE = ROOT / "dashboard" / "data.json"
LOCATION_FILE = ROOT / "dashboard" / "location.json"
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


def sanitize_err(e: Exception) -> str:
    """Error text safe for PUBLIC Actions logs: exception type plus a short,
    single-line excerpt. Never a traceback — request internals could leak."""
    msg = " ".join(str(e).split())
    return f"{type(e).__name__}: {msg[:120]}"


def write_json_atomic(path: Path, obj) -> None:
    """Write via temp file + os.replace so a killed run can never leave a
    truncated JSON file behind for the workflow to commit or deploy."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, default=str))
    os.replace(tmp, path)


# ─── Reverse geocoding (free via Nominatim) ────────────────────────────────
def reverse_geocode(lat: float, lng: float) -> str | None:
    """Return a short human-readable place name for (lat, lng), or None.
    Uses OpenStreetMap Nominatim. No API key required, but the policy
    requires a real User-Agent identifying the app. Coordinates are
    rounded to 3 decimals (~100 m) — zoom 14 doesn't need more, and the
    third party doesn't need a sub-meter fix."""
    try:
        params = urllib.parse.urlencode({
            "lat": f"{lat:.3f}",
            "lon": f"{lng:.3f}",
            "format": "json",
            "zoom": "14",  # neighborhood / suburb level
            "addressdetails": "1",
        })
        url = f"https://nominatim.openstreetmap.org/reverse?{params}"
        req = urllib.request.Request(url, headers={
            "User-Agent": "garage-uconnect/1.0 (https://github.com/YamesMacK/garage-uconnect)",
            "Accept-Language": "en-US",
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.load(resp)

        addr = data.get("address") or {}
        # Build a "City, State" or "Suburb, City" — short and readable
        city = (
            addr.get("city")
            or addr.get("town")
            or addr.get("village")
            or addr.get("hamlet")
            or addr.get("suburb")
            or addr.get("neighbourhood")
            or addr.get("county")
        )
        state = addr.get("state_code") or addr.get("state")
        # Abbreviate state if it's a US full name
        US_STATE_ABBR = {
            "Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR",
            "California": "CA", "Colorado": "CO", "Connecticut": "CT", "Delaware": "DE",
            "Florida": "FL", "Georgia": "GA", "Hawaii": "HI", "Idaho": "ID",
            "Illinois": "IL", "Indiana": "IN", "Iowa": "IA", "Kansas": "KS",
            "Kentucky": "KY", "Louisiana": "LA", "Maine": "ME", "Maryland": "MD",
            "Massachusetts": "MA", "Michigan": "MI", "Minnesota": "MN", "Mississippi": "MS",
            "Missouri": "MO", "Montana": "MT", "Nebraska": "NE", "Nevada": "NV",
            "New Hampshire": "NH", "New Jersey": "NJ", "New Mexico": "NM", "New York": "NY",
            "North Carolina": "NC", "North Dakota": "ND", "Ohio": "OH", "Oklahoma": "OK",
            "Oregon": "OR", "Pennsylvania": "PA", "Rhode Island": "RI", "South Carolina": "SC",
            "South Dakota": "SD", "Tennessee": "TN", "Texas": "TX", "Utah": "UT",
            "Vermont": "VT", "Virginia": "VA", "Washington": "WA", "West Virginia": "WV",
            "Wisconsin": "WI", "Wyoming": "WY", "District of Columbia": "DC",
        }
        if state in US_STATE_ABBR:
            state = US_STATE_ABBR[state]

        if city and state:
            return f"{city}, {state}"
        if city:
            return city
        # Fall back to display_name's first two comma-separated parts
        dn = data.get("display_name") or ""
        parts = [p.strip() for p in dn.split(",")]
        if parts:
            return ", ".join(parts[:2]) if len(parts) >= 2 else parts[0]
    except Exception as e:
        print(f"  · reverse-geocode failed: {sanitize_err(e)}")
    return None


def load_prev_locations() -> dict:
    """Previous location.json (the workflow curls the last-good copy from the
    live site before the poll). Used to skip Nominatim when parked."""
    if LOCATION_FILE.exists():
        try:
            return json.loads(LOCATION_FILE.read_text()).get("locations") or {}
        except (json.JSONDecodeError, AttributeError):
            return {}
    return {}


def resolve_place(vin: str, lat: float, lng: float, prev_locations: dict) -> str | None:
    """Reuse the previous place name when the truck hasn't moved (~50 m),
    so Nominatim isn't hit every 30 minutes while parked."""
    prev = prev_locations.get(vin) or {}
    try:
        if (
            prev.get("place")
            and abs(float(prev["lat"]) - lat) < 5e-4
            and abs(float(prev["lng"]) - lng) < 5e-4
        ):
            return prev["place"]
    except (TypeError, ValueError, KeyError):
        pass
    return reverse_geocode(lat, lng)


# ─── Oil baseline ──────────────────────────────────────────────────────────
def load_oil_baseline() -> dict:
    if OIL_BASELINE_FILE.exists():
        try:
            return json.loads(OIL_BASELINE_FILE.read_text())
        except json.JSONDecodeError as e:
            # Do NOT fall back to {} — that would silently re-anchor the
            # baseline to the current odometer and wipe real oil tracking.
            print(f"ERROR: {OIL_BASELINE_FILE} is corrupted ({e}); refusing to "
                  "auto-anchor over it. Fix or delete the file deliberately.",
                  file=sys.stderr)
            sys.exit(1)
    return {}


def save_oil_baseline(baseline: dict) -> None:
    write_json_atomic(OIL_BASELINE_FILE, baseline)


def compute_oil(vin: str, odometer_mi, baseline: dict):
    entry = baseline.get(vin)
    # Tolerate the legacy bare-number form; write the structured form back
    # so the file self-upgrades on the next commit.
    if isinstance(entry, (int, float)):
        entry = {"odometer_at_last_change_mi": entry}
        baseline[vin] = entry

    if odometer_mi is None:
        # Keep the block shape constant so the dashboard can tell "no
        # odometer this poll" apart from "fresh oil change".
        return ({
            "interval_mi": OIL_CHANGE_INTERVAL_MILES,
            "baseline_mi": entry.get("odometer_at_last_change_mi") if entry else None,
            "miles_since": None,
            "miles_to_next": None,
            "baseline_set_at": entry.get("set_at") if entry else None,
            "auto_anchored": entry.get("auto_anchored", False) if entry else False,
        }, baseline)

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
def apply_remote_status(vehicle: Vehicle, status: dict) -> None:
    """Map the get_vehicle_status (remote/status) payload onto the Vehicle.
    Mirrors what client.refresh() does internally — doors/windows/engine/
    trunk state lives on this endpoint only. Every field is optional."""
    def _eq(d: dict, *path, value):
        cur = d
        for k in path:
            if not isinstance(cur, dict):
                return None
            cur = cur.get(k)
        if cur is None:
            return None
        return cur == value

    doors = status.get("doors") or {}
    vehicle.door_driver_locked = _eq(doors, "driver", "status", value="LOCKED")
    vehicle.door_passenger_locked = _eq(doors, "passenger", "status", value="LOCKED")
    vehicle.door_rear_left_locked = _eq(doors, "leftRear", "status", value="LOCKED")
    vehicle.door_rear_right_locked = _eq(doors, "rightRear", "status", value="LOCKED")

    windows = status.get("windows") or {}
    vehicle.window_driver_closed = _eq(windows, "driver", "status", value="CLOSED")
    vehicle.window_passenger_closed = _eq(windows, "passenger", "status", value="CLOSED")

    engine_on = _eq(status, "engine", "status", value="ON")
    if engine_on is not None:
        vehicle.ignition_on = engine_on

    trunk = _eq(status, "trunk", "status", value="LOCKED")
    if trunk is not None:
        vehicle.trunk_locked = trunk


def fetch_vehicle(client, vin_entry: dict) -> Vehicle:
    """Build a populated Vehicle for a single VIN without using
    client.refresh() (extra calls, and historically it crashed on the
    broken Challenger)."""
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
    if not info:
        # py-uconnect 0.4.x returns {} on HTTP 400/404/502 instead of
        # raising. Treat that as a failed fetch, not an all-null vehicle.
        raise RuntimeError("get_vehicle returned an empty payload")
    _update_vehicle(vehicle, info)

    # Doors/windows/engine state — separate endpoint, best-effort.
    try:
        status = client.api.get_vehicle_status(vin)
        if status:
            apply_remote_status(vehicle, status)
    except Exception as e:
        print(f"  · {vin}: no remote status ({sanitize_err(e)})")

    # Location is a separate API call; tolerate failure.
    try:
        loc = client.api.get_vehicle_location(vin)
        updated = (
            datetime.fromtimestamp(loc["timeStamp"] / 1000, tz=timezone.utc)
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


def aggregate_locked(*states):
    """False if ANY reported door is unlocked; True only when ALL doors are
    explicitly reported locked; None otherwise. A partial payload must never
    render as a false-safe LOCKED."""
    if any(s is False for s in states):
        return False
    if all(s is True for s in states):
        return True
    return None


# ─── Per-vehicle serializer ────────────────────────────────────────────────
def serialize_vehicle(v: Vehicle, oil_baseline: dict, prev_locations: dict):
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

    # Location goes to location.json (NOT committed), never data.json.
    location = None
    if v.location:
        lat = to_float(v.location.latitude)
        lng = to_float(v.location.longitude)
        if lat is not None and lng is not None:
            location = {
                "lat": lat,
                "lng": lng,
                "ts": v.location.updated.isoformat() if v.location.updated else None,
                "place": resolve_place(v.vin, lat, lng, prev_locations),
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
        # Post-subscription-upgrade telemetry — null until the truck reports it.
        "ignition_on": v.ignition_on,
        "doors_locked": aggregate_locked(
            v.door_driver_locked, v.door_passenger_locked,
            v.door_rear_left_locked, v.door_rear_right_locked,
        ),
        "days_to_service": to_int(v.days_to_service),
        "service_mi": normalize_distance(v.distance_to_service, v.distance_to_service_unit),
        "oil_level_pct": to_int(v.oil_level),
        "oil": oil_block,
    }, location, oil_baseline)


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
        print(f"ERROR listing vehicles: {sanitize_err(e)}", file=sys.stderr)
        sys.exit(1)

    oil_baseline = load_oil_baseline()
    baseline_before = json.dumps(oil_baseline, sort_keys=True, default=str)
    prev_locations = load_prev_locations()
    vehicles_out = []
    locations_out = {}

    for entry in listed:
        vin = entry.get("vin")
        if not vin:
            continue
        if vin not in ALLOWED_VINS:
            print(f"  · {vin} — skipped (not in allowlist)")
            continue

        try:
            vehicle = fetch_vehicle(client, entry)
            vd, loc, oil_baseline = serialize_vehicle(vehicle, oil_baseline, prev_locations)
            vehicles_out.append(vd)
            if loc:
                locations_out[vin] = loc
            mtn = (vd.get("oil") or {}).get("miles_to_next")
            print(f"  ✓ {vin}: odo={vd.get('odometer_mi')} mi · oil_to_next={mtn} mi")
        except Exception as e:
            print(f"  ! {vin}: fetch failed — {sanitize_err(e)}", file=sys.stderr)

    if not vehicles_out:
        print("No vehicles fetched successfully — leaving data.json untouched", file=sys.stderr)
        sys.exit(1)

    now_iso = datetime.now(timezone.utc).isoformat()
    write_json_atomic(DATA_FILE, {
        "last_updated": now_iso,
        "vehicles": vehicles_out,
    })
    print(f"Wrote {DATA_FILE}")

    # Preserve last-good fixes for VINs that didn't report one this poll.
    for vin, prev in prev_locations.items():
        locations_out.setdefault(vin, prev)
    if locations_out:
        write_json_atomic(LOCATION_FILE, {
            "last_updated": now_iso,
            "locations": locations_out,
        })
        print(f"Wrote {LOCATION_FILE}")
    else:
        # Monotonic: never deploy an EMPTY location set over a possibly
        # nonempty one (curl of last-good can miss AND the location call can
        # fail in the same run). Leaving the file alone keeps whatever the
        # workflow fetched; absence just renders "No fix" on the dashboard.
        print("No locations this poll and no last-good copy — leaving location.json untouched")

    if json.dumps(oil_baseline, sort_keys=True, default=str) != baseline_before:
        save_oil_baseline(oil_baseline)
        print(f"Wrote {OIL_BASELINE_FILE} (baseline changed)")


if __name__ == "__main__":
    main()
