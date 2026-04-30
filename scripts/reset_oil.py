"""
reset_oil.py — Re-anchor the oil-change baseline to the current odometer.

Triggered by the "Reset Oil" button in the dashboard via workflow_dispatch.
Reads the most recent odometer from dashboard/data.json and writes a new
dashboard/oil_baseline.json with that value, then commits.

After the next 30-min poll, miles_to_next will read 5,000 again.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent
DATA_FILE = ROOT / "dashboard" / "data.json"
OIL_BASELINE_FILE = ROOT / "dashboard" / "oil_baseline.json"


def main() -> None:
    if not DATA_FILE.exists():
        print(f"ERROR: {DATA_FILE} does not exist — can't determine current odometer", file=sys.stderr)
        sys.exit(1)

    try:
        data = json.loads(DATA_FILE.read_text())
    except json.JSONDecodeError as e:
        print(f"ERROR: data.json is malformed — {e}", file=sys.stderr)
        sys.exit(1)

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

        baseline[vin] = {
            "odometer_at_last_change_mi": round(odo),
            "set_at": datetime.now(timezone.utc).isoformat(),
            "auto_anchored": False,  # user-initiated, not auto
        }
        updated_vins.append((vin, round(odo)))
        print(f"  ✓ {vin}: baseline reset to {round(odo)} mi")

    if not updated_vins:
        print("No vehicles updated — leaving baseline file untouched", file=sys.stderr)
        sys.exit(1)

    OIL_BASELINE_FILE.parent.mkdir(parents=True, exist_ok=True)
    OIL_BASELINE_FILE.write_text(json.dumps(baseline, indent=2))
    print(f"Wrote {OIL_BASELINE_FILE}")


if __name__ == "__main__":
    main()
