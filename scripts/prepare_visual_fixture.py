#!/usr/bin/env python3
"""Validate visual fixtures and print the locked local preview URL."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = REPO_ROOT / "visual-lock" / "fixtures"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--port",
        type=int,
        default=4174,
        help="Local repository-root server port. Defaults to 4174.",
    )
    args = parser.parse_args()

    data_text = (FIXTURES / "data.json").read_text(encoding="utf-8")
    data = json.loads(data_text.replace("__NOW__", "2000-01-01T00:00:00+00:00"))
    location = json.loads((FIXTURES / "location.json").read_text(encoding="utf-8"))
    if "__NOW__" not in data_text:
        raise SystemExit("data.json must retain the __NOW__ placeholder")
    if not data.get("vehicles"):
        raise SystemExit("data.json must contain one visual-lock vehicle")
    if "locations" not in location:
        raise SystemExit("location.json must contain a locations object")

    print(f"http://127.0.0.1:{args.port}/dashboard/?visual-lock=1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
