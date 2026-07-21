# Garage — Ram 2500 Dashboard

Personal iPhone PWA dashboard for the 2022 Ram 2500. Polls the Stellantis cloud
directly via [`py-uconnect`](https://github.com/hass-uconnect/py-uconnect). Runs
on free GitHub Actions + free GitHub Pages. Not affiliated with any employer.

```
[Stellantis cloud]  ←── login (Mopar email/password/PIN)
        ↓
[poll.py in GitHub Actions every 30 min]
        ↓
[data.json committed · location.json deployed only (never committed)]
        ↓
[GitHub Pages serves the PWA from /dashboard]
        ↓
[iPhone home screen icon → reads data.json + location.json]
        ↓
[lock / unlock / start / stop / horn / locate → workflow_dispatch → send_command.py]
```

## What this Ram reports

| Metric | Status | Notes |
|---|---|---|
| Odometer | ✅ | km from API → mi |
| Range to empty | ✅ | km → mi |
| Fuel level % | ✅ | |
| Fuel low warning | ✅ | Boolean from truck |
| Battery voltage | ✅ | |
| Tire pressure (all 4) | ✅ | kPa → PSI |
| Tire warnings | ✅ | Per-corner boolean |
| GPS location | ✅ | Lat/lng + timestamp (location.json, not committed) |
| Door lock state | ❓ | Polled from the remote-status endpoint since the plan upgrade; tile appears once the truck reports it |
| Ignition state | ❓ | Same — best-effort from remote status |
| Days/miles to dealer service | ❓ | Shown under Odometer once non-null |
| Window state | ❌ | Not reported so far |

Run `scripts/test_connection.py` after a subscription change to dump exactly
what the account returns now, and diff it against this table.

The Mopar account also has a 2023 Dodge Challenger that errors on
every status call. It's filtered out by the VIN allowlist in `scripts/poll.py`.

## Oil change tracking — 5,000 mi baseline

The dashboard ignores the truck's reported oil-life percentage for the DUE
calculation (it's shown as a small secondary readout when available) and uses
a fixed **5,000 mile** interval against a baseline odometer reading stored in
`dashboard/oil_baseline.json`.

- On the first poll for a new VIN, the baseline auto-anchors to the current
  odometer (and the workflow commits it). The dashboard reads "5,000 mi to
  next change" until you drive.
- After your next oil change, hit the **Reset** pill on the Oil tile (fires
  `reset_oil.yml` → `scripts/reset_oil.py`), or run
  `scripts/reset_oil_baseline.py` from a PC. The reset re-anchors the
  baseline, rewrites data.json's oil block, and chains a poll + Pages
  deploy — the pill tracks the run and the tile reads 5,000 again in
  ~3 minutes.
- The "Oil · 5K" tile shows miles remaining; turns red and reads "DUE" once
  past 5,000 mi since the baseline.

## Remote commands from the dashboard

The command buttons fire a `workflow_dispatch` against
[`.github/workflows/command.yml`](.github/workflows/command.yml), which runs
`scripts/send_command.py` on a GitHub-hosted runner with the Mopar secrets.
`send_command.py` uses py-uconnect's `command_verify()`, so the workflow run
only succeeds if the **truck acknowledges** the command — and the dashboard
polls the run and toasts the real outcome.

### One-time setup

Because the dashboard is a static PWA in a public repo, the GitHub API call
needs a token. The token lives in your iPhone's `localStorage` only — never
committed to the repo.

1. Visit https://github.com/settings/personal-access-tokens/new
2. Choose **Fine-grained personal access token**
3. Resource owner: your account · Repository access: **Only select repositories**
   → `YamesMacK/garage-uconnect`
4. Repository permissions → **Actions: Read and write** (everything else: No access)
5. Set an expiration (90 days is fine; you can rotate)
6. Generate, copy the token (`github_pat_…`)
7. Open the dashboard on your phone → **settings** in the footer → paste → Save

The token is now stored on that device only. Clear it from the same panel.

### What each button does

| Button | py-uconnect command | Notes |
|---|---|---|
| Lock | `COMMAND_DOORS_LOCK` | |
| Unlock | `COMMAND_DOORS_UNLOCK` | Confirmation prompt |
| Start | `COMMAND_ENGINE_ON` | Remote-start; truck runs ~10 min. Confirmation prompt |
| Stop | `COMMAND_ENGINE_OFF` | Cancels a remote start. Confirmation prompt |
| Horn | `COMMAND_LIGHTS_HORN` | Horn + lights ("find my truck"). Confirmation prompt |
| Locate | `COMMAND_REFRESH_LOCATION` | Fresh GPS fix; a poll run is chained ~45 s later so the map updates in ~2-3 min |

`command.yml` also accepts `lights` (flash only, no horn) and `deep_refresh`
(force the truck to push full fresh telemetry) from the Actions tab or CLI.
Each command takes ~1.5-2.5 min end to end (Actions cold-start, then
`command_verify` waits for the truck's ack). The button spinner runs until
the workflow finishes and the toast reports the truck's answer.

You can also fire commands from your PC — see `scripts/send_command.py`.

## Setup checklist

### 1. Mopar credentials → GitHub Secrets

Repo → Settings → Secrets and variables → Actions → New repository secret.

| Secret | Value |
|---|---|
| `MOPAR_EMAIL` | Mopar account email |
| `MOPAR_PASSWORD` | Mopar account password |
| `MOPAR_PIN` | 4-digit Mopar PIN |

### 2. Enable GitHub Pages

Repo → Settings → Pages → Source: **GitHub Actions**.

### 3. Watch the first poll run

Actions tab → "Poll Ram & Deploy Dashboard" runs at :07 and :37 each hour
(offset from the congested :00/:30 scheduler slots, which GitHub drops
liberally). First run takes ~90 seconds. Dashboard URL appears at
Settings → Pages.

### 4. Install on iPhone

1. Open the URL in **Safari** (Chrome can't install PWAs)
2. Share → Add to Home Screen
3. Tap the icon — opens fullscreen like a native app

## File map

```
garage-uconnect/
├─ scripts/
│  ├─ poll.py                  # Polling script (CI). 5k oil tracker lives here.
│  ├─ test_connection.py       # One-off diagnostic — dumps everything the API returns
│  ├─ reset_oil.py             # Re-anchor baseline + data.json oil block (Reset pill via reset_oil.yml)
│  ├─ reset_oil_baseline.py    # CLI variant — hits Stellantis for a live odometer
│  └─ send_command.py          # CLI + CI: lock/unlock/start/stop/horn/locate/deep_refresh
├─ dashboard/
│  ├─ index.html               # PWA shell, telemetry rendering, and command UI
│  ├─ redesign.css             # Editorial GARAGE visual system and mobile layout
│  ├─ manifest.json
│  ├─ sw.js                    # Service worker (network-first shell + data)
│  ├─ icon-192.png · icon-512.png
│  ├─ img/                     # White-truck hero + top-down tire-pressure art
│  ├─ proto/                   # 9 design prototypes (proto 9 became the live UI)
│  ├─ data.json                # ← Updated by poll.py every 30 min (committed)
│  ├─ location.json            # ← GPS fix — deployed to Pages only, NEVER committed
│  └─ oil_baseline.json        # Per-VIN baseline odometer for 5k tracker
├─ .github/workflows/
│  ├─ poll.yml                 # Cron + Pages deploy (poll job / deploy job split)
│  ├─ command.yml              # workflow_dispatch for remote commands
│  └─ reset_oil.yml            # workflow_dispatch for the Reset pill
├─ .github/dependabot.yml      # Keeps SHA-pinned actions + py-uconnect current
├─ requirements.txt            # py-uconnect, exact-pinned
├─ .env.example                # Not auto-loaded — reference for env vars
├─ .gitignore
└─ README.md
```

## VIN allowlist

`poll.py`, `reset_oil_baseline.py`, and `send_command.py` reference the Ram's
VIN explicitly. To add a vehicle, edit `ALLOWED_VINS` in `poll.py` /
`reset_oil_baseline.py` and `TARGET_VIN` in `send_command.py`. The dashboard
frontend currently renders only `data.vehicles[0]` — multi-vehicle support
needs a small layout change.

## Troubleshooting

**Dashboard shows "STALE"** — Check the Actions tab for the latest poll run.
"STALE" means data.json is older than 90 minutes; cron runs at :07/:37 so
you should normally be < 35 min fresh. (GitHub throttles schedules under
load; occasional gaps are normal.)

**Authentication failed in Actions** — Re-create the three Mopar secrets at
Settings → Secrets and variables → Actions.

**A command button does nothing** — Open the in-app settings panel and
verify the GitHub PAT is set. If it is, check the Actions tab for the latest
"Send vehicle command" run; py-uconnect's auth or the truck modem may be
the actual blocker. A run that FAILS after ~60 s usually means the truck
rejected or never acked the command (asleep modem, out of cell coverage).

**Challenger errors** — Filtered out by the VIN allowlist. Likely expired
connected services subscription or a sleeping modem.

**Tire pressures wrong** — Should be 65–80 PSI for a 2500. If you see ~30,
the kPa → PSI conversion broke. Check the raw `unit` field in the API
response and adjust `normalize_pressure()` in `poll.py`.

**Stale GPS** — The truck only updates location when it wakes up. Tap
**Locate** on the dashboard (or `python scripts/send_command.py
refresh_location`) to force a fresh fix; the map updates ~2-3 min later.

## Caveats

- **py-uconnect is reverse-engineered.** Stellantis can break it any time.
  The dependency is exact-pinned; Dependabot proposes bumps.
- **Mopar password sits in GitHub Secrets.** Encrypted at rest, never logged,
  but it is a credential. Rotate periodically.
- **Public repo, public Pages.** The Pages URL is derivable from the repo
  name — assume anyone can read the dashboard. Current GPS fix is served
  from `location.json` on Pages (needed for the map), but it is **not
  committed**, so git history no longer accumulates a movement log.
  Pre-2026-07 history still contains old fixes; purging it requires a
  history rewrite (`git filter-repo`) — owner's call.
- **PAT lives in iPhone localStorage.** If the device is compromised, the
  attacker can fire workflow_dispatch on this repo — which now includes
  **remote start and unlock**. Keep the PAT expiration short and revoke at
  https://github.com/settings/personal-access-tokens to kill it instantly.
- **No real-time data.** Cron runs every 30 minutes (GitHub may skip some).
  For live data, use the Mopar app — or tap Locate / fire `deep_refresh`.
