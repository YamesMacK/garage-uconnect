#!/usr/bin/env python3
"""Verify protected visual sources and optionally compare candidate screenshots."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
LOCK_FILE = REPO_ROOT / "visual-lock" / "visual-lock.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_sha256(path: Path) -> str:
    if path.suffix.lower() in {".css", ".json"}:
        normalized = path.read_text(encoding="utf-8")
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    return sha256(path)


def visual_surface_sha256() -> str:
    html = (REPO_ROOT / "dashboard" / "index.html").read_text(encoding="utf-8")
    active_start = html.index("</template>") + len("</template>")
    script_start = html.index("<script>", active_start)
    script_end = html.index("</script>", script_start) + len("</script>")

    head_tokens = "\n".join(
        line.strip()
        for line in html[:active_start].splitlines()
        if any(
            token in line
            for token in (
                "theme-color",
                "apple-mobile-web-app",
                "Roboto+Condensed",
                "cinematic.css",
            )
        )
    )
    surface = (
        head_tokens
        + "\n"
        + html[active_start:script_start]
        + "\n"
        + html[script_start:script_end]
    )
    return hashlib.sha256(surface.encode("utf-8")).hexdigest()


def compare_images(reference: Path, candidate: Path, config: dict) -> tuple[bool, str]:
    try:
        from PIL import Image, ImageChops, ImageStat
    except ModuleNotFoundError as exc:
        if exc.name == "PIL":
            raise SystemExit(
                "Screenshot comparison requires Pillow. Install it with: "
                "python -m pip install -r requirements-visual-lock.txt"
            ) from exc
        raise

    with Image.open(reference) as ref_image, Image.open(candidate) as candidate_image:
        ref = ref_image.convert("RGB")
        current = candidate_image.convert("RGB")
        if ref.size != current.size:
            return False, f"dimension mismatch {current.size} != {ref.size}"

        diff = ImageChops.difference(ref, current)
        mean_delta = sum(ImageStat.Stat(diff).mean) / 3
        red, green, blue = diff.split()
        max_channel = ImageChops.lighter(ImageChops.lighter(red, green), blue)
        threshold = int(config["pixel_delta_threshold"])
        changed = max_channel.point(lambda value: 255 if value > threshold else 0)
        histogram = changed.histogram()
        changed_pixels = histogram[255]
        total_pixels = ref.size[0] * ref.size[1]
        changed_ratio = changed_pixels / total_pixels

        passed = (
            mean_delta <= float(config["max_mean_channel_delta"])
            and changed_ratio <= float(config["max_changed_pixel_ratio"])
        )
        detail = (
            f"changed={changed_ratio:.3%}, mean-channel-delta={mean_delta:.3f}"
        )
        return passed, detail


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--candidate-dir",
        type=Path,
        help="Folder containing iphone-393.png, iphone-320.png, and settings-393.png.",
    )
    args = parser.parse_args()

    if not LOCK_FILE.exists():
        raise SystemExit(f"Visual lock manifest is missing: {LOCK_FILE}")
    lock = json.loads(LOCK_FILE.read_text(encoding="utf-8"))

    failures: list[str] = []
    print("Visual source lock")
    for relative, expected in lock["protected_files"].items():
        path = REPO_ROOT / relative
        if not path.exists():
            failures.append(f"missing protected file: {relative}")
            continue
        actual = source_sha256(path)
        status = "PASS" if actual == expected else "FAIL"
        print(f"  {status} {relative}")
        if actual != expected:
            failures.append(f"protected file changed: {relative}")

    surface_actual = visual_surface_sha256()
    surface_status = (
        "PASS" if surface_actual == lock["visual_surface_sha256"] else "FAIL"
    )
    print(f"  {surface_status} active HTML/render surface")
    if surface_status == "FAIL":
        failures.append("active HTML/render surface changed")

    baseline_dir = REPO_ROOT / "visual-lock" / "baselines"
    for filename, metadata in lock["baselines"].items():
        path = baseline_dir / filename
        if not path.exists():
            failures.append(f"missing baseline: {filename}")
            continue
        actual = sha256(path)
        if actual != metadata["sha256"]:
            failures.append(f"baseline changed: {filename}")

    if args.candidate_dir:
        candidate_dir = args.candidate_dir.resolve()
        print("Screenshot comparison")
        for filename in lock["comparison_files"]:
            reference = baseline_dir / filename
            candidate = candidate_dir / filename
            if not candidate.exists():
                failures.append(f"missing candidate screenshot: {filename}")
                continue
            passed, detail = compare_images(
                reference,
                candidate,
                lock["comparison"],
            )
            print(f"  {'PASS' if passed else 'FAIL'} {filename}: {detail}")
            if not passed:
                failures.append(f"visual mismatch: {filename} ({detail})")

    if failures:
        print("\nVisual lock FAILED:", file=sys.stderr)
        for failure in failures:
            print(f"  - {failure}", file=sys.stderr)
        print(
            "Do not update the lock or baselines without James's explicit visual approval.",
            file=sys.stderr,
        )
        return 1

    print("Visual lock PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
