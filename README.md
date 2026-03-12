# Dashboard Builder

Standalone, containerized Python manager for ESP32-C6 e-ink dashboard devices.

## What is implemented

- Basic authentication (login session) for web UI tabs.
- Tabbed UI:
  - `Designer`
  - `Device Management`
  - `Integrations`
- Designer capabilities:
  - base layout seeded from original firmware style
  - live browser preview
  - drag + resize section blocks in preview canvas
  - preview modes: `Layout Only` and `Real Data` (cached manager data)
  - advanced mode for manual controls and section JSON tuning
  - section templates: weather, headlines, quote of the day, calendar upcoming
- Device management capabilities:
  - add/remove devices
  - assign dashboard to device
  - per-device profile overrides
  - rotate device token
  - raw-device provisioning with claim code
- Flashing/provisioning support:
  - firmware image catalog in UI
  - generated command workflow for flashing
  - bootstrap claim API endpoint: `POST /api/provision/claim`
- Integrations catalog:
  - original firmware defaults (Open-Meteo, wttr, NWS, Google/Reuters RSS, ZenQuotes)
  - alternate templates (Google Calendar, AccuWeather, OpenWeather, WeatherAPI, NewsAPI)

## Quick start

```bash
cp .env.example .env
docker compose up --build -d
docker compose ps
```

## Docker Scripts (Windows/Mac/Linux)

Use these scripts from a Bash shell:

- Windows: Git Bash or WSL (`bash ./scripts/<name>.sh`)
- macOS/Linux: Terminal (`./scripts/<name>.sh`)

```bash
# Start (build + run)
./scripts/up.sh

# Check service + health
./scripts/status.sh

# Follow logs (default service: dashboard-manager)
./scripts/logs.sh

# Restart with rebuild
./scripts/restart.sh

# Stop (add --volumes to remove volumes)
./scripts/down.sh
```

Optional remote context (example):

```bash
DOCKER_CONTEXT=personal ./scripts/up.sh
```

Open:

- UI: `http://localhost:8000/`
- API docs: `http://localhost:8000/docs`
- Health: `http://localhost:8000/health`

Default login:

- Username: `admin`
- Password: `change-me`

Change credentials in `.env`:

- `ADMIN_USERNAME`
- `ADMIN_PASSWORD`
- `SESSION_SECRET`

## LXC host note

If you run Docker remotely in an LXC host, use a remote Docker context:

```bash
docker context create personal --docker "host=ssh://<user>@<lxc-host-ip>"
docker --context personal compose up --build -d
```

## Key paths

- `app/main.py`: UI routes + API routes
- `app/templates/`: web UI templates
- `app/services/integrations.py`: provider adapters
- `app/services/rendering.py`: device manifest composition
- `docs/FIRMWARE_CONTRACT.md`: manager/firmware contract
- `docs/CODEX_PLATFORMIO_PROMPTS.md`: codex prompts for PlatformIO tasks