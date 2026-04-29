# Garage — Ram 2500 Dashboard

iPhone PWA dashboard for the 2022 Ram 2500. Polls Stellantis cloud directly via
[`py-uconnect`](https://github.com/hass-uconnect/py-uconnect). Runs on free
GitHub Actions + free GitHub Pages.

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
```

## What this version reports for your specific Ram

Confirmed working from your test_connection output:

| Metric | Status | Notes |
|---|---|---|
| Odometer | ✅ | 142,990 mi at last check |
| Range to empty | ✅ | 248 mi |
| Fuel level % | ✅ | 65% |
| Fuel low warning | ✅ | Boolean flag from truck |
| **Oil life %** | ✅ | **63% — direct from truck**, no baseline math needed |
| Battery voltage | ✅ | 13.6V |
| Tire pressure (all 4) | ✅ | Auto-converted kPa → PSI |
| Tire warnings | ✅ | Per-corner boolean |
| GPS location | ✅ | Lat/lng + last-updated timestamp |
| Door lock state | ❌ | Not reported by your truck |
| Window state | ❌ | Not reported |
| Ignition state | ❌ | Not reported |
| Days/miles to dealer service | ❌ | Truck reports null |

Your Mopar account also has a **2023 Dodge Challenger** that returns HTTP 502
on every status call. It's been added to the allowlist as **excluded** — poll.py
skips it automatically. If you ever fix whatever's causing that 502 (modem
asleep, expired subscription, etc.), add its VIN to `ALLOWED_VINS` in
`scripts/poll.py` to include it.

## Setup checklist

### 1. Create the GitHub repository

```powershell
cd C:\Users\JamesMacKinnon\Desktop\garage-uconnect

# Create empty repo on github.com first (private recommended), then:
git init
git add .
git commit -m "Initial garage dashboard"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/garage-uconnect.git
git push -u origin main
```

### 2. Add Mopar credentials as GitHub Secrets

Repo → Settings → Secrets and variables → Actions → New repository secret.

| Secret name | Value |
|---|---|
| `MOPAR_EMAIL` | Your Mopar account email |
| `MOPAR_PASSWORD` | Your Mopar account password |
| `MOPAR_PIN` | Your 4-digit Mopar PIN |

### 3. Enable GitHub Pages

Repo → Settings → Pages → Source: **GitHub Actions** (not "Deploy from branch").

### 4. Push and watch the first run

```powershell
git push
```

Go to the **Actions** tab. Watch "Poll Ram & Deploy Dashboard" run. First run
typically takes ~90 seconds. When it succeeds, your dashboard URL appears at
Settings → Pages.

### 5. Install on iPhone

1. Open the URL in **Safari** (not Chrome — only Safari can install PWAs)
2. Share button → Add to Home Screen
3. Done — tap the home screen icon and it opens fullscreen like a native app

## File map

```
garage-uconnect/
├─ scripts/
│  ├─ poll.py                  # Main polling script (runs in CI)
│  ├─ test_connection.py       # One-off diagnostic — already verified working
│  ├─ reset_oil_baseline.py    # Optional, only needed if truck stops reporting oil life
│  └─ send_command.py          # CLI: lock/unlock/start the truck remotely
├─ dashboard/
│  ├─ index.html               # The PWA (single file, embedded CSS/JS)
│  ├─ manifest.json            # PWA install metadata
│  ├─ sw.js                    # Service worker for offline cache
│  ├─ icon-192.png             # PWA icon (small)
│  ├─ icon-512.png             # PWA icon (large)
│  ├─ data.json                # ← Updated by poll.py every 30 min
│  └─ oil_baseline.json        # ← Optional fallback for oil tracking
├─ .github/workflows/
│  └─ poll.yml                 # Cron schedule + Pages deploy
├─ requirements.txt            # Just py-uconnect
├─ .env.example                # Template for local dev
├─ .gitignore
└─ README.md                   # This file
```

## Remote commands

`send_command.py` lets you lock/unlock and remote-start from your PC. Same
data path the iPhone Mopar app uses.

```powershell
$env:MOPAR_EMAIL = "you@example.com"
$env:MOPAR_PASSWORD = "your_password"
$env:MOPAR_PIN = "1234"

python scripts\send_command.py lock
python scripts\send_command.py unlock
python scripts\send_command.py engine_on
python scripts\send_command.py engine_off
python scripts\send_command.py lights_horn       # honk + flash
python scripts\send_command.py refresh_location  # force GPS refresh
```

## VIN allowlist

`poll.py`, `reset_oil_baseline.py`, and `send_command.py` all reference your
Ram's VIN explicitly. If you ever swap trucks or want to add more vehicles,
edit `ALLOWED_VINS` near the top of `poll.py` (and `reset_oil_baseline.py`)
and `TARGET_VIN` in `send_command.py`.

The allowlist also keeps the Challenger from breaking the poll. If you
ever sort out whatever's wrong with the Challenger (502 error on every
status call), add its VIN to the allowlist and the dashboard frontend will
need a small update to handle multi-vehicle layout.

## Troubleshooting

**Dashboard shows "STALE"**
- Check the Actions tab — did the latest run succeed?
- A poll fails when py-uconnect's auth fails or the API returns an error.
  Click the failed run to see the exact error.
- "Stale" means data.json is more than 90 minutes old. Cron runs every 30m
  so you should always be <30m fresh.

**`Authentication failed` in Actions**
- Confirm the three secrets (`MOPAR_EMAIL`, `MOPAR_PASSWORD`, `MOPAR_PIN`)
  exist at Settings → Secrets and variables → Actions
- Re-create them if unsure — secrets can't be viewed after creation
- Mopar can rate-limit if py-uconnect retries too fast. Wait 15 minutes.

**HTTP 502 on the Challenger**
- Already filtered out by the VIN allowlist. Ignore.
- If you want the Challenger to work, the underlying issue is likely:
  - Connected services subscription expired (check Mopar account)
  - Modem hasn't connected in a while (drive it 10 min, try again)
  - The car was deactivated from the account at some point

**Tire pressures look wrong**
- Should be 65-80 PSI for a 2500. If you see ~30, the conversion broke.
  Check `test_output.json` to see the raw `pressure.unit` field — if it's
  not `kPa`, edit `normalize_pressure()` in poll.py.

**Stale GPS location**
- Location updates only when the truck wakes up. To force a fresh reading:
  `python scripts\send_command.py refresh_location`

## Risks / honest caveats

- **py-uconnect is reverse-engineered.** Stellantis could break it any time.
  Maintainers are responsive (last release Mar 2026, 28 versions shipped),
  but a 1-2 week outage if Mopar changes auth is plausible.
- **Mopar password sits in GitHub Secrets.** Encrypted at rest, never logged,
  but it's a credential. If that bothers you, run poll.py via Windows Task
  Scheduler on your home PC instead and skip GitHub Actions.
- **GitHub Pages exposes data.json publicly.** The URL is unguessable but
  discoverable if your repo is public. Recommend making the **repo private**
  (GitHub Pages still works for private repos on Pro, $4/mo).
- **No real-time updates.** Cron runs every 30 minutes. If you need live
  data, open the Mopar app — that's what they built.
