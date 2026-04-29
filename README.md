# Garage — Ram 2500 Dashboard

Personal iPhone PWA dashboard for the 2022 Ram 2500. Polls the Stellantis cloud
directly via [`py-uconnect`](https://github.com/hass-uconnect/py-uconnect). Runs
on free GitHub Actions + free GitHub Pages. Not affiliated with any employer.

```
[Stellantis cloud]  ←── login (Mopar email/password/PIN)
        ↓
[poll.py in GitHub Actions every 30 min]
        ↓
[dashboard/data.json committed to repo]
        ↓
[GitHub Pages serves the PWA from /dashboard]
        ↓
[iPhone home screen icon → reads data.json]
        ↓
[lock / unlock / start buttons → workflow_dispatch → send_command.py]
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
| GPS location | ✅ | Lat/lng + timestamp |
| Door lock state | ❌ | Not reported by this truck |
| Window state | ❌ | Not reported |
| Ignition state | ❌ | Not reported |
| Days/miles to dealer service | ❌ | Reports null |

The Mopar account also has a 2023 Dodge Challenger that returns HTTP 502 on
every status call. It's filtered out by the VIN allowlist in `scripts/poll.py`.

## Oil change tracking — 5,000 mi baseline

The dashboard ignores the truck's reported oil-life percentage and uses a
fixed **5,000 mile** interval against a baseline odometer reading stored in
`dashboard/oil_baseline.json`.

- On the first poll for a new VIN, the baseline auto-anchors to the current
  odometer. The dashboard will read "5,000 mi to next change" until you drive.
- After your next oil change, run `scripts/reset_oil_baseline.py` (or hit the
  Reset pill on the dashboard once that's wired) to anchor the baseline to
  the odometer reading at the moment of the change.
- The "Oil · 5k" tile shows miles remaining; turns red and reads "DUE" once
  past 5,000 mi since the baseline.

## Remote commands from the dashboard

The Lock / Unlock / Start buttons fire a `workflow_dispatch` against
[`.github/workflows/command.yml`](.github/workflows/command.yml), which runs
`scripts/send_command.py` on a GitHub-hosted runner with the Mopar secrets.

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
| Unlock | `COMMAND_DOORS_UNLOCK` | |
| Start | `COMMAND_ENGINE_ON` | Remote-start; truck runs ~10 min |

Each command takes 30–60s end to end (GitHub Actions cold-start ~20s,
Stellantis acks the truck ~10–30s). The button shows a pending state until
the dispatch returns.

You can also fire commands from your PC — see the script at
`scripts/send_command.py`.

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

Actions tab → "Poll Ram & Deploy Dashboard" runs every 30 min. First run
takes ~90 seconds. Dashboard URL appears at Settings → Pages.

### 4. Install on iPhone

1. Open the URL in **Safari** (Chrome can't install PWAs)
2. Share → Add to Home Screen
3. Tap the icon — opens fullscreen like a native app

## File map

```
garage-uconnect/
├─ scripts/
│  ├─ poll.py                  # Polling script (CI). 5k oil tracker lives here.
│  ├─ test_connection.py       # One-off diagnostic
│  ├─ reset_oil_baseline.py    # Re-anchor oil baseline after a change
│  └─ send_command.py          # CLI: lock/unlock/start (also runs in CI)
├─ dashboard/
│  ├─ index.html               # The PWA (single file, embedded CSS/JS)
│  ├─ manifest.json
│  ├─ sw.js                    # Service worker (cached shell, live data.json)
│  ├─ icon-192.png · icon-512.png
│  ├─ data.json                # ← Updated by poll.py every 30 min
│  └─ oil_baseline.json        # Per-VIN baseline odometer for 5k tracker
├─ .github/workflows/
│  ├─ poll.yml                 # Cron + Pages deploy
│  └─ command.yml              # workflow_dispatch for lock/unlock/start
├─ requirements.txt
├─ .env.example
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
"STALE" means data.json is older than 90 minutes; cron runs every 30m so
you should always be < 30m fresh.

**Authentication failed in Actions** — Re-create the three Mopar secrets at
Settings → Secrets and variables → Actions.

**Lock/Unlock/Start does nothing** — Open the in-app settings panel and
verify the GitHub PAT is set. If it is, check the Actions tab for the latest
"Send vehicle command" run; py-uconnect's auth or the truck modem may be
the actual blocker.

**HTTP 502 on the Challenger** — Filtered out by the VIN allowlist. Likely
expired connected services subscription or a sleeping modem.

**Tire pressures wrong** — Should be 65–80 PSI for a 2500. If you see ~30,
the kPa → PSI conversion broke. Check the raw `unit` field in the API
response and adjust `normalize_pressure()` in `poll.py`.

**Stale GPS** — The truck only updates location when it wakes up. To force:
`python scripts/send_command.py refresh_location` (or wire it to a button).

## Caveats

- **py-uconnect is reverse-engineered.** Stellantis can break it any time.
- **Mopar password sits in GitHub Secrets.** Encrypted at rest, never logged,
  but it is a credential. Rotate periodically.
- **Public repo, public Pages.** The URL is unguessable but discoverable.
  Anyone with it can read VIN, odometer, GPS, fuel/oil/battery state.
  They cannot send commands without a PAT scoped to this repo.
- **PAT lives in iPhone localStorage.** If the device is compromised, the
  attacker can fire workflow_dispatch on this repo. Revoke the token at
  https://github.com/settings/tokens to kill it instantly.
- **No real-time data.** Cron runs every 30 minutes. For live data, use
  the Mopar app.
