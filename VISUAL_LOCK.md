# Approved visual contract

Status: **LOCKED**

Approved by James MacKinnon on July 24, 2026. This contract protects the
cinematic iPhone interface from accidental redesign.

## Source of truth

The approved evidence is stored in `visual-lock/baselines/`:

- `approved-concept.png` — original cinematic direction (794×1981)
- `iphone-393.png` — 393px Browser viewport; 378×1092 full-page artifact
  after the Browser excludes its 15px persistent scrollbar gutter
- `iphone-320.png` — 320px Browser viewport; 320×1058 viewport artifact;
  the current Browser uses an overlay scrollbar at this narrow width
- `settings-393.png` — 393px Browser viewport and 393×1132 full-page artifact
  because the open sheet locks page scrolling

The implementation screenshots override the concept wherever the concept
conflicts with the corrections below.

## Locked design decisions

- iPhone-first, portrait-only composition; no desktop redesign is required.
- Cinematic pearl-white Ram hero on a dark mountain road.
- Vehicle identity: **2022 RAM 2500** and **Laramie Crew Cab 4x4**.
- The overhead Laramie asset has **no sunroof**.
- Dark graphite surfaces, restrained copper accents, subtle borders and
  shadows, and condensed automotive typography.
- Section order:
  1. hero and freshness
  2. Range, Fuel, Odometer, Battery
  3. Next Oil Change
  4. Tire Pressure
  5. Command Center
  6. Status
  7. Location
  8. Settings and Reload Data
- Command Center grouping remains Access / Engine / Find with all six commands.
- Start Engine remains the centered circular primary control.
- Oil mileage uses a second line for `mi remaining`.
- The oil card shows only miles remaining until the next oil change; do not
  add a redundant oil-life percentage or replacement metric.
- Range shows miles to empty only. The Fuel percentage card is the only
  telemetry card with a fuel-level bar, using the labeled E-to-F treatment.
- The oil graphic is the approved iOS-style asset at
  `dashboard/img/oil-can-ios.png`; do not redraw or substitute it.
- The tire graphic remains large, centered, and aligned with all four readings.
- Status retains its copper ring, detail affordance, and expandable text.
- With a GPS fix, the Location panel shows the truck's map position and the
  entire panel opens those coordinates in Google Maps.
- The embedded Google map uses its native colors at full opacity for legibility.
- Minimum interactive target size is 44 by 44 CSS pixels.
- No horizontal overflow at 393px or 320px.

## Permitted variation

Live telemetry, timestamps, warnings, status text, addresses, map content, and
unknown-data states may change. These are data changes, not redesigns.

Accessibility fixes and functional repairs are allowed only when they preserve
the locked composition and pass the visual gate.

For deterministic captures, serve the repository root locally and open
`/dashboard/?visual-lock=1`. This localhost-only mode replaces live values with
the fixtures under `visual-lock/fixtures/`; it cannot activate on the deployed
app.

## Approval rule

Never replace a baseline or update `visual-lock/visual-lock.json` merely
because a comparison failed. A new baseline requires James to see the changed
screens and explicitly approve the new appearance.
