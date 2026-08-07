# CLAUDE.md

Guidance for Claude Code and other AI assistants working in this repository.

`AGENTS.md` is the short, non-negotiable contract — read it too. This file is
the long-form explanation of *why* those rules exist and how everything fits
together.

---

## 1. What this repo is

A personal iPhone PWA dashboard for one truck — a 2022 Ram 2500 Laramie Crew
Cab 4x4 (no sunroof). It has **no server and no framework**. Everything is
static files plus scheduled GitHub Actions.

```
[Stellantis / Mopar cloud]   ← py-uconnect, login = email + password + PIN
        ↓  every 30 min (cron :07 / :37 UTC)
[scripts/poll.py in GitHub Actions]
        ↓
[dashboard/data.json  → committed to main]
[dashboard/location.json → deployed to Pages ONLY, never committed]
        ↓
[GitHub Pages serves ./dashboard as the site root]
        ↓
[iPhone home-screen PWA reads data.json + location.json]
        ↓
[6 command buttons → GitHub API workflow_dispatch → scripts/send_command.py]
```

Live site: `https://yamesmack.github.io/garage-uconnect/`
Repo constant in the frontend: `REPO = 'YamesMacK/garage-uconnect'`

**Stack:** Python 3.12 (CI) with exactly one runtime dependency
(`py-uconnect==0.4.6`); vanilla HTML/CSS/JS with zero build step, zero npm, zero
bundler. Keep it that way — "preserve the dependency-free static PWA
architecture" is an explicit project rule.

---

## 2. Read this first: the visual lock

**The iPhone interface is frozen under an approval contract.** This is the
single most important constraint in the repository and the one most likely to
be violated by an assistant acting helpfully.

Before touching *any* frontend file, run:

```bash
py -3 scripts/check_visual_lock.py
```

It must print `Visual lock PASSED` before you start, so you know your baseline.

### The rules (from `AGENTS.md` / `VISUAL_LOCK.md`)

- The screenshots in `visual-lock/baselines/` are the visual source of truth.
- Do **not** restyle, modernize, simplify, substitute icons, reorder sections,
  or "clean up" the design. Not as a side effect of a bug fix either.
- Do **not** update a baseline or `visual-lock/visual-lock.json` to make a
  failing gate pass. A new baseline requires James to look at the changed
  screens and explicitly approve them.
- Keep frontend changes **local** until James explicitly authorizes commit,
  push, or deployment. (Docs-only changes like this file are not frontend
  changes and follow normal git flow.)
- One editing agent only. Product / iPhone / design / QA agents are read-only
  reviewers.
- The truck is a 2022 Ram 2500 Laramie, **no sunroof**. Use
  `dashboard/img/oil-can-ios.png` for the oil graphic — don't redraw it.

### Locked composition

Section order is part of the contract: hero + freshness → Range, Fuel,
Odometer, Battery → Next Oil Change → Tire Pressure → Command Center (Access /
Engine / Find, with Start Engine as the centered circular primary) → Status →
Location → Settings and Reload Data. Minimum tap target 44×44 CSS px. No
horizontal overflow at 393px or 320px. Full list in `VISUAL_LOCK.md`.

Live telemetry, timestamps, warnings, status text, addresses and map content
*may* change — those are data changes, not redesigns.

### What the gate actually checks

`scripts/check_visual_lock.py` has two modes.

**Source mode** (no arguments, no third-party deps):

1. SHA-256 of every entry in `protected_files` — `dashboard/cinematic.css`,
   `manifest.json`, both icons, four images, and both `visual-lock/fixtures/`
   files. `.css`/`.json` are hashed as decoded text (line-ending independent);
   PNGs are hashed as raw bytes.
2. The **active render surface** of `dashboard/index.html`, hashed as:
   everything through `</head>` + the markup between `</template>` and
   `<script>` + the entire `<script>` block. The `<template id="legacy-shell">`
   body is excluded.
3. Baseline PNGs are still PNG-encoded and still match their recorded hashes.

> Consequence worth internalizing: **any** edit to index.html's head, live
> markup, or JavaScript changes `visual_surface_sha256` and fails the gate —
> even a pure logic fix that renders identically. That is intentional. It
> forces the screenshot workflow below rather than silent frontend drift.

**Comparison mode** (`--candidate-dir <folder>`) additionally diffs your
screenshots against the baselines using Pillow, with the thresholds in
`visual-lock/visual-lock.json`: per-pixel delta > 18 counts as changed, ≤ 1.2%
of pixels may change, mean channel delta ≤ 1.5.

### Required workflow for an authorized frontend change

```bash
py -3 -m pip install -r requirements-visual-lock.txt        # Pillow, QA only
py -3 scripts/prepare_visual_fixture.py --port 4174         # validates fixtures, prints URL
py -3 -m http.server 4174 --bind 127.0.0.1 --directory .    # serve REPO ROOT, not dashboard/
```

Open the printed `http://127.0.0.1:4174/dashboard/?visual-lock=1`. That mode is
localhost-only and swaps live data for `visual-lock/fixtures/`, so captures are
deterministic. Capture at the locked sizes:

| File | Viewport | Artifact |
|---|---|---|
| `iphone-393.png` | 393 px | 378×1090 full page |
| `iphone-320.png` | 320 px | 320×1058 viewport |
| `settings-393.png` | 393 px, Settings sheet open | 393×1132 full page |

Then `py -3 scripts/check_visual_lock.py --candidate-dir <folder>`. **Stop if
it fails.** Show James the comparison and get explicit approval before changing
the lock, committing, pushing, or deploying.

The gate's source-only mode also runs in CI (`.github/workflows/visual-lock.yml`,
added 2026-08-06 — audit finding F-028), on every push and pull request, so a
change that fails it can't land silently. CI only runs the no-args mode; it
can't do the `--candidate-dir` screenshot comparison (that needs a served
fixture and a real browser capture), so the discipline above is still what
catches a visual regression that keeps the surface hash the same.

---

## 3. Repository layout

```
garage-uconnect/
├─ AGENTS.md                  # Non-negotiable agent contract (read it)
├─ VISUAL_LOCK.md             # The approved design contract
├─ CLAUDE.md                  # This file
├─ README.md                  # Owner-facing setup, troubleshooting, caveats
├─ THIRD_PARTY_NOTICES.md     # Icons8 attribution for oil-can-ios.png
├─ requirements.txt           # py-uconnect==0.4.6 (production, exact-pinned)
├─ requirements-visual-lock.txt  # Pillow==12.3.0 (visual QA only)
├─ .env.example               # Reference only — nothing auto-loads it
├─ scripts/
│  ├─ poll.py                 # CI poller; owns the 5k oil tracker
│  ├─ send_command.py         # CLI + CI: the 8 remote commands
│  ├─ reset_oil.py            # CI: re-anchor baseline from data.json
│  ├─ reset_oil_baseline.py   # CLI variant: re-anchor from a live API odometer
│  ├─ test_connection.py      # Diagnostic: dump everything the API returns
│  ├─ probe_capabilities.py   # Diagnostic: sanitized service-code probe
│  ├─ check_visual_lock.py    # The visual gate
│  └─ prepare_visual_fixture.py  # Validates fixtures, prints the locked URL
├─ dashboard/                 # ← this directory IS the deployed Pages site
│  ├─ index.html              # Whole PWA: markup + JS (CSS is external)
│  ├─ cinematic.css           # The locked stylesheet
│  ├─ sw.js                   # Service worker
│  ├─ manifest.json
│  ├─ icon-192.png · icon-512.png
│  ├─ img/                    # hero + top-down truck art, oil icon
│  ├─ proto/                  # 9 dead design prototypes (proto 9 → live UI)
│  ├─ data.json               # written by poll.py, committed
│  ├─ location.json           # written by poll.py, gitignored
│  └─ oil_baseline.json       # per-VIN baseline odometer
├─ visual-lock/
│  ├─ visual-lock.json        # hashes + thresholds + baseline dimensions
│  ├─ baselines/*.png         # approved screenshots
│  └─ fixtures/               # deterministic data for ?visual-lock=1
└─ .github/
   ├─ workflows/{poll,command,reset_oil,diagnose_capabilities,visual-lock}.yml
   └─ dependabot.yml
```

`dashboard/proto/` is a museum of abandoned prototypes. It ships to Pages but
nothing links to it. Don't take styling cues from it — proto 9 was the ancestor
of the live UI, but `cinematic.css` superseded all of them.

---

## 4. Data contracts

### `dashboard/data.json` (committed)

```jsonc
{
  "last_updated": "<ISO8601 UTC>",
  "vehicles": [{
    "vin": "...", "year": "2022", "make": "Ram", "model": "2500", "nickname": null,
    "odometer_mi": 152088.0, "range_mi": 69.0,
    "fuel_pct": 22, "fuel_low": false, "battery_v": 12.8,
    "tires_psi":     { "front_left": 62.0, "front_right": 66.0, "rear_left": 66.0, "rear_right": 66.0 },
    "tires_warning": { "front_left": true, "front_right": false, "rear_left": false, "rear_right": false },
    "ignition_on": null,        // best-effort, from a separate endpoint
    "doors_locked": null,       // null | true | false — see aggregate_locked()
    "days_to_service": null, "service_mi": null,
    "oil_level_pct": 86,        // truck's own reading — INFORMATIONAL ONLY
    "oil": {
      "interval_mi": 5000, "baseline_mi": 150917,
      "miles_since": 1171, "miles_to_next": 3829,
      "baseline_set_at": "<ISO8601>", "auto_anchored": false
    }
  }]
}
```

All distances are **miles**, pressures **PSI**, converted in `poll.py`.
`null` means *not reported* and must render as `—`, never as a confident `0`.

### `dashboard/location.json` (gitignored, Pages-only)

```json
{ "last_updated": "<ISO>", "locations": { "<VIN>": { "lat": 0.0, "lng": 0.0, "ts": "<ISO>", "place": "City, ST" } } }
```

GPS deliberately never enters public git history. `poll.yml` curls the previous
copy off the live site before polling, and re-fetches it before deploying, so a
Pages deploy can't erase the last-known fix. **Never** commit this file or move
location back into `data.json`.

### `dashboard/oil_baseline.json` (committed)

```json
{ "<VIN>": { "odometer_at_last_change_mi": 150917, "set_at": "<ISO>", "auto_anchored": false } }
```

`auto_anchored: true` means poll.py anchored it automatically on first sight of
a VIN; `false` means a human reset it after an actual oil change.

---

## 5. The dashboard (frontend)

`dashboard/index.html` is one file with four regions:

| Lines (approx) | Region | Notes |
|---|---|---|
| 1–535 | `<head>` | CSP, fonts, **and a `<style media="not all">` block** |
| 537–665 | `<template id="legacy-shell">` | Dead old UI, excluded from the lock hash |
| 667–823 | Live markup | `.card` → hero, `#grid`, Command Center, Status, Location, utility rows, Settings sheet, toast |
| 825–1701 | `<script>` | All behavior |

Traps in this file:

- The head `<style media="not all">` is **inert** (that media query never
  matches). The real stylesheet is `cinematic.css`. Editing that dead block
  changes nothing visually but *does* break the surface hash.
- **There are two `function render()` declarations** — one at ~954 (legacy) and
  one at ~1169 (cinematic). The later declaration wins, so the first one and
  its helpers (`ICON_OIL`, `ICON_BATT`) are dead code. Edit the second one.
  If you delete the first, expect a lock-hash change and screenshot re-approval.
- The stylesheet is cache-busted by query string:
  `<link rel="stylesheet" href="cinematic.css?v=20260724f">`, and `sw.js`
  precaches the identical string. Change one, change the other, and bump
  `CACHE` in `sw.js`.

### Rendering rules

- Only `data.vehicles[0]` is rendered. Multi-vehicle support would need layout
  work.
- Thresholds baked into the UI: data older than **90 min** → `stale`; GPS fix
  older than **180 min** → warn + "use Locate"; battery **< 12.4 V** → Low;
  oil `miles_to_next <= 0` → `DUE`, `< 500` → "change soon".
- The Ignition/Doors tiles only appear once the truck actually reports them.
- Any externally-sourced string (place names from OpenStreetMap) must go
  through `esc()` before `innerHTML`. The CSP is deliberately tight because a
  PAT in `localStorage` can start the engine.

### Commands

`COMMANDS` in index.html must mirror `command.yml`'s `type: choice` options.
Six are wired to buttons: `lock`, `unlock`, `engine_on`, `engine_off`,
`lights_horn`, `refresh_location`. `lights` and `deep_refresh` exist in
`send_command.py` and `command.yml` but have no button. Anything that moves
metal or makes noise carries a `confirm:` prompt (pocket-tap guard).

Flow: `dispatch()` POSTs `workflow_dispatch` with a random correlation `tag` →
`trackRun()` polls the runs list every 5 s for up to 3 minutes and matches
**its own tag** in the run name → on failure `readRunResult()` reads the job's
step names and extracts the result class.

> **Invariant:** the dashboard parses the literal step name
> `` `Truck App result: <class>` `` out of the GitHub jobs API. Renaming that
> step in `command.yml`, or changing the `^Truck App result: ([a-z_]+)$` regex
> on one side only, silently breaks all command feedback.

Result classes come from **three** places, and the two lists deliberately do
**not** match. Do not "sync" them into one:

- `RESULTS` in `send_command.py` is the allowlist of classes *the script* may
  emit through `GITHUB_OUTPUT`. It includes `confirmed` and `rejected`.
- `command.yml` can mint a class the script never emits: the result step falls
  back to `workflow_setup` when the command step was skipped, and to `timeout`
  when the step produced no output at all.
- `COMMAND_RESULT_MESSAGES` in index.html holds the *toast copy* for the
  classes that need a generic message. It therefore omits `confirmed` (the
  success path) and `rejected` (which falls through to the per-command
  `rejected` string in `COMMANDS`), and it includes `workflow_setup`, which
  `send_command.py` has no way to produce.

The real rule: every class reachable by the dashboard — whether emitted by
`send_command.py` or minted by `command.yml` — needs either an entry in
`COMMAND_RESULT_MESSAGES` or a deliberate fall-through in
`commandResultMessage()`. Adding a class to `RESULTS` means checking that path;
it does not mean copying the name into both files.

The PAT lives in `localStorage['gh_pat']` on the phone only. It is never
committed and never leaves the device except as a GitHub API `Authorization`
header. Never add code that logs, echoes, or transmits it anywhere else.

### Service worker (`sw.js`)

Network-first for `data.json` / `location.json` (cached under a *canonical*
key, because the page fetches with a `?t=` buster), network-first for
navigations so deploys land without a cache bump, cache-first for everything
else same-origin. Cross-origin requests pass straight through.

---

## 6. The scripts (backend)

All read credentials from env vars `MOPAR_EMAIL`, `MOPAR_PASSWORD`,
`MOPAR_PIN`. Nothing auto-loads `.env` — there is no python-dotenv. Set real
env vars locally; CI uses repository secrets of the same names.

### `poll.py` — the important one

Deliberate design choices that must not be regressed (they're documented in the
module docstring too):

- Does **not** call `client.refresh()`. It builds each `Vehicle` manually via
  `client.api.get_vehicle(vin)` + `_update_vehicle()`, so one broken sibling
  vehicle can't kill the whole poll and we skip per-vehicle calls we don't need.
- py-uconnect 0.4.x returns `{}` (not an exception) on HTTP 400/404/502. An
  empty dict **must** be treated as a failed fetch, or the poll writes an
  all-null row over good data.
- Non-obvious py-uconnect attribute names: tire pressure is
  `wheel_front_left_pressure` (not `tire_pressure_*`), fuel percentage is
  `fuel_amount` (not `fuel_level_percent`), oil life is `oil_level`.
- Doors / windows / engine come from a **separate** endpoint
  (`get_vehicle_status`), called best-effort.
- `aggregate_locked()` returns `False` if any door reports unlocked, `True`
  only if all four explicitly report locked, else `None`. A partial payload
  must never render a false-safe "LOCKED".
- `sanitize_err()` exists because Actions logs are public — never print
  tracebacks or raw API payloads.
- `write_json_atomic()` (temp file + `os.replace`) so a killed run can't leave
  truncated JSON for the workflow to commit.
- A corrupt `oil_baseline.json` is a **hard exit**, not a fallback to `{}` —
  falling back would silently re-anchor the baseline and wipe oil tracking.
- Reverse geocoding uses Nominatim with a real User-Agent, coordinates rounded
  to 3 decimals, and reuses the cached place name when the truck has moved
  < ~50 m, so it isn't hit every 30 minutes while parked.
- If no vehicle fetches successfully, it exits 1 and leaves `data.json` alone.

### `send_command.py`

Uses `client.command_verify()`, so success means the **truck acknowledged**,
not that the request was accepted. Exceptions are mapped by
`classify_exception()` into one of the allowlisted `RESULTS` classes and
emitted via `GITHUB_OUTPUT` — never raw Stellantis responses.

### `reset_oil.py` vs `reset_oil_baseline.py`

- `reset_oil.py` (CI, fired by the Reset control) reads the odometer from
  `data.json`, refuses data older than `MAX_DATA_AGE_HOURS = 6`, and rewrites
  **both** `oil_baseline.json` and the `oil` block inside `data.json` so the
  reset appears on the very next Pages deploy.
- `reset_oil_baseline.py` (PC/CLI) hits Stellantis for a live odometer instead
  and only writes the baseline; you commit and push it yourself.
- `OIL_CHANGE_INTERVAL_MILES = 5000` is duplicated in `poll.py` and
  `reset_oil.py`. **Change both together.**

### Diagnostics

- `test_connection.py` — dumps everything the account returns to
  `test_output.json` (gitignored). Run after any subscription change and diff
  against the capability table in `README.md`.
- `probe_capabilities.py` — read-only, prints service codes only; no VIN,
  identity, location, or credentials. Wired to `diagnose_capabilities.yml`.

---

## 7. GitHub Actions

| Workflow | Trigger | Permissions | Purpose |
|---|---|---|---|
| `poll.yml` | cron `7,37 * * * *` (UTC), `workflow_dispatch`, push to `main` | poll job `contents:write`; deploy job `pages:write` + `id-token:write` | Poll → commit data.json → deploy Pages |
| `command.yml` | `workflow_dispatch` (`command`, `tag`) | `contents:read`, `actions:write` | Send one vehicle command |
| `reset_oil.yml` | `workflow_dispatch` (`tag`) | `contents:write`, `actions:write` | Re-anchor the oil baseline |
| `diagnose_capabilities.yml` | `workflow_dispatch` | `contents:read` | Sanitized capability probe |
| `visual-lock.yml` | `push`, `pull_request`, `workflow_dispatch` | `contents:read` | Source-only visual gate check (F-028) |

Details that look odd but are deliberate:

- Cron is `:07/:37`, not `*/30` — GitHub drops a large share of runs scheduled
  on the congested `:00/:30` slots.
- `concurrency: pages` with `cancel-in-progress: false` — Pages can't deploy
  concurrently and cancelling mid-deploy can wedge the environment.
- The poll step is `continue-on-error: true` so a Stellantis outage still lets
  shell/PWA updates deploy.
- Permissions are split across jobs so the pip-installed third-party code in
  the poll job can never mint an OIDC token.
- Both commit steps retry pushes 5×, but with **opposite** conflict strategies:
  `poll.yml` rebases with `-X theirs` (keep this run's fresh telemetry);
  `reset_oil.yml` deliberately does **not** — it hard-resets to fresh `main`
  and re-runs `reset_oil.py`, so a concurrent poll's newer telemetry survives
  and only the oil block changes. Don't "unify" these.
- Bot commits carry `[skip ci]`, and `GITHUB_TOKEN` pushes don't retrigger
  workflows anyway; chained runs use explicit `gh workflow run` dispatches
  (exempt from the no-recursion rule).
- `command.yml` passes the input through an env var (`CMD`) instead of
  interpolating it into the shell line — injection defense-in-depth on top of
  `type: choice`.
- Actions are pinned to full commit SHAs with a version comment. Dependabot
  bumps them weekly along with pip. Keep the SHA pinning.

---

## 8. Development workflows

There is **no test suite, linter, formatter, or build step.** Verification is:

```bash
py -3 scripts/check_visual_lock.py                 # always, before and after frontend work
py -3 -c "import json; json.load(open('dashboard/data.json'))"   # JSON sanity
py -3 -m http.server 4174 --bind 127.0.0.1 --directory .          # serve from REPO ROOT
```

The fixture route resolves `../visual-lock/fixtures/...`, which is why the
server must be rooted at the repo, not at `dashboard/`.

Anything that talks to the truck needs real Mopar credentials in the
environment. Do not attempt to exercise `send_command.py` (it moves a real
vehicle) without explicit instruction — and never as a "quick check".

**Python-side changes** (scripts, workflows) follow normal git flow: commit and
push with a clear message. **Frontend changes** additionally require the
screenshot gate and James's approval before commit/push/deploy.

---

## 9. Conventions and invariants

Preserve unless explicitly told otherwise:

1. No dependencies added to the frontend. No npm, no bundler, no framework, no
   CDN scripts. The CSP would block them anyway.
2. `requirements.txt` stays exact-pinned — this runs on a schedule with real
   credentials and a `contents:write` token; upgrades are Dependabot PRs
   reviewed deliberately.
3. The six vehicle commands, telemetry set, Settings, Reload Data, offline
   behavior, and current data contracts all stay.
4. GPS never enters git. `dashboard/location.json` stays gitignored.
5. Public Actions logs get sanitized errors only — never tracebacks, raw
   payloads, VINs beyond what's already public in the repo, or credentials.
6. `null` telemetry renders as unknown, never as a confident zero.
7. Miles and PSI at the boundary; all conversion happens in `poll.py`.
8. Keep the paired constants in sync: interval miles (`poll.py` /
   `reset_oil.py`), command list (`index.html` / `command.yml` /
   `send_command.py`), the `Truck App result:` step name (`command.yml` /
   `index.html`), and the CSS cache-bust string (`index.html` / `sw.js`).
   Result classes are the exception — `RESULTS` and `COMMAND_RESULT_MESSAGES`
   are intentionally different sets; see §5.

### The VIN

`3C6UR5FJ6NG305274` is hardcoded in four *operative* places:
`scripts/poll.py` (`ALLOWED_VINS`), `scripts/reset_oil_baseline.py`
(`ALLOWED_VINS`), `scripts/send_command.py` (`TARGET_VIN`), and
`.github/workflows/diagnose_capabilities.yml` (`MOPAR_VIN`). The allowlist
exists to filter out a sibling 2023 Dodge Challenger on the same Mopar account
that errors on every status call. Adding a vehicle means editing all four *and*
the dashboard layout.

Those four are the ones that *do* anything. If the task is instead to remove
the VIN from this public repo, grep for it — it also appears in two dead
prototypes (`dashboard/proto/2-cluster.html`, `dashboard/proto/8-tesla.html`)
and in the committed data (`dashboard/data.json`, `dashboard/oil_baseline.json`,
`visual-lock/fixtures/data.json`, plus the gitignored `location.json`). Four is
the answer for adding a vehicle; ten is the answer for scrubbing one.

---

## 10. Gotchas

- **A "harmless" JS fix still fails the visual gate.** The whole `<script>` is
  inside the hashed surface. Plan for the screenshot workflow.
- **Dead code is load-bearing for the hash.** The legacy `<style media="not
  all">` block, the `<template>`, the first `render()` — deleting them is a
  lock-affecting change even though nothing renders differently.
- **`?visual-lock=1` only works on localhost** and can't activate on the
  deployed site. It also swaps in a fixture with `locations: {}`, so the
  Location panel renders its no-fix state in the baselines.
- **Safari date parsing:** `parseTs()` rewrites `"YYYY-MM-DD HH:MM:SS"` to ISO
  because old polls emitted a space separator and Safari rejects it. Keep it.
- **Tire pressures should read 65–80 PSI** on a 2500. If they read ~30, the
  kPa→PSI conversion regressed — check the `unit` field and
  `normalize_pressure()`.
- **"STALE" on the dashboard** usually means GitHub throttled the cron, not
  that the code broke. Check the Actions tab first.
- **`.env.example` is documentation, not configuration.** Nothing loads it.
- **The CSP allows more than fonts and maps.** The permitted external origins
  are `fonts.googleapis.com` (stylesheet) and `fonts.gstatic.com` (font files)
  under `style-src`/`font-src`; `maps.google.com` and `www.google.com` under
  `frame-src`; and **`api.github.com` and `raw.githubusercontent.com` under
  `connect-src`**. `api.github.com` is load-bearing — every command dispatch
  and every run-status poll goes through it, so a CSP "tightening" that drops
  it kills the whole Command Center. `raw.githubusercontent.com` was added by
  commit `14a0a49` ("Decouple dashboard data from Pages deploys") alongside
  the new `LIVE_DATA_URL` fetch. Adding an origin means editing the CSP,
  which is inside the hashed surface — and that commit is exactly why the
  lock currently fails; see F-008, operator decision, not fixed here.
