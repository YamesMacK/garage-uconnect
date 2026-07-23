# Truck App visual lock

This repository contains an explicitly approved iPhone interface. Before
editing any frontend file, read `VISUAL_LOCK.md` and run:

```powershell
python scripts/check_visual_lock.py
```

## Non-negotiable workflow

- Treat the screenshots in `visual-lock/baselines/` as the visual source of
  truth.
- Do not restyle, modernize, simplify, substitute icons, reorder sections, or
  update a baseline unless James explicitly approves that visual change.
- Preserve the dependency-free static PWA architecture.
- Preserve the six vehicle commands, telemetry, Settings, Reload Data,
  offline behavior, and current data contracts.
- The truck is a 2022 Ram 2500 Laramie with no sunroof.
- Use `dashboard/img/oil-can-ios.png` for the oil-change graphic.
- Keep visual changes local until James explicitly authorizes commit, push, or
  deployment.
- Use one editing agent. Product, iPhone, design, and QA agents must be
  read-only reviewers.

## Required visual validation

For any authorized frontend change:

1. Validate the deterministic fixtures and print the locked URL with
   `python scripts/prepare_visual_fixture.py --port 4174`.
2. Serve the repository root on that port with
   `python -m http.server 4174 --bind 127.0.0.1 --directory .`.
3. Open the printed `?visual-lock=1` URL in the in-app Browser at the locked
   393px and 320px widths. The fixture route only activates on localhost.
4. Capture the dashboard, narrow dashboard, and open Settings sheet using the
   filenames documented in `VISUAL_LOCK.md`.
5. Run
   `python scripts/check_visual_lock.py --candidate-dir <screenshot-folder>`.
6. Stop if the gate fails. Do not update the baselines to make a failure pass.
7. Show James the comparison and obtain explicit approval before changing the
   lock, committing, pushing, or deploying.
