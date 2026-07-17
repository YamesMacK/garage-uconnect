"""
reset_oil.py — Re-anchor the oil-change baseline to the current odometer.

Triggered by the "Reset Oil" button in the dashboard via workflow_dispatch.
Reads the most recent odometer from dashboard/data.json and writes a new
dashboard/oil_baseline.json with that value.

Also rewrites the `oil` block inside data.json itself (the dashboard tile
renders data.json, not oil_baseline.json) so the reset is visible as soon
as the workflow's chained Pages deploy lands — not only after the next
cron poll happens to run.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent
DATA_FILE = ROOT / "dashboard" / "data.json"
OIL_BASELINE_FILE = ROOT / "dashboard" / "oil_baseline.json"

# Must match OIL_CHANGE_INTERVAL_MILES in poll.py.
OIL_CHANGE_INTERVAL_MILES = 5000

# Refuse to anchor to an odometer reading older than this — a stale anchor
# writes a silently-wrong baseline. Cron polls every 30 min, so anything
# past 6 h means polling is broken; fix that first.
MAX_DATA_AGE_HOURS = 6


def main() -> None:
    if not DATA_FILE.exists():
        print(f"ERROR: {DATA_FILE} does not exist — can't determine current odometer", file=sys.stderr)
        sys.exit(1)

    try:
        data = json.loads(DATA_FILE.read_text())
    except json.JSONDecodeError as e:
        print(f"ERROR: data.json is malformed — {e}", file=sys.stderr)
        sys.exit(1)

    last_updated = data.get("last_updated")
    if last_updated:
        try:
            age_h = (datetime.now(timezone.utc)
                     - datetime.fromisoformat(str(last_updated))).total_seconds() / 3600
            print(f"  · data.json is {age_h:.1f} h old")
            if age_h > MAX_DATA_AGE_HOURS:
                print(f"ERROR: odometer reading is {age_h:.1f} h old (max {MAX_DATA_AGE_HOURS} h). "
                      "Run the poll workflow first, then reset again.", file=sys.stderr)
                sys.exit(1)
        except ValueError:
            print(f"  · couldn't parse last_updated={last_updated!r}; proceeding without freshness check")

    vehicles = data.get("vehicles") or []
    if not vehicles:
        print("ERROR: no vehicles in data.json", file=sys.stderr)
        sys.exit(1)

    # Load existing baseline so we don't clobber other VINs
    baseline = {}
    if OIL_BASELINE_FILE.exists():
        try:
            baseline = json.loads(OIL_BASELINE_FILE.read_text())
        except json.JSONDecodeError:
            baseline = {}

    updated_vins = []
    for v in vehicles:
        vin = v.get("vin")
        odo = v.get("odometer_mi")
        if not vin or odo is None:
            print(f"  · skipping {vin}: no odometer reading")
            continue

        entry = {
            "odometer_at_last_change_mi": round(odo),
            "set_at": datetime.now(timezone.utc).isoformat(),
            "auto_anchored": False,  # user-initiated, not auto
        }
        baseline[vin] = entry
        # Same block shape as compute_oil() in poll.py — the tile renders
        # this, so the reset shows up on the very next Pages deploy.
        v["oil"] = {
            "interval_mi": OIL_CHANGE_INTERVAL_MILES,
            "baseline_mi": entry["odometer_at_last_change_mi"],
            "miles_since": 0,
            "miles_to_next": OIL_CHANGE_INTERVAL_MILES,
            "baseline_set_at": entry["set_at"],
            "auto_anchored": False,
        }
        updated_vins.append((vin, round(odo)))
        print(f"  ✓ {vin}: baseline reset to {round(odo)} mi")

    if not updated_vins:
        print("No vehicles updated — leaving baseline file untouched", file=sys.stderr)
        sys.exit(1)

    OIL_BASELINE_FILE.parent.mkdir(parents=True, exist_ok=True)
    OIL_BASELINE_FILE.write_text(json.dumps(baseline, indent=2))
    print(f"Wrote {OIL_BASELINE_FILE}")

    # last_updated is left alone on purpose — the odometer still dates from
    # the last poll; only the derived oil block changed.
    DATA_FILE.write_text(json.dumps(data, indent=2, default=str))
    print(f"Wrote {DATA_FILE} (oil block re-anchored)")


if __name__ == "__main__":
    main()
