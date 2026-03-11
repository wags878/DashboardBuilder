# Dashboard Builder

Standalone, containerized Python backend for managing e-ink dashboards and ESP32-C6 display devices.

## What this starter includes

- FastAPI service with SQLite persistence.
- Data model for templates, dashboards, devices, and assignments.
- Device heartbeat and signed manifest pull endpoints.
- In-process scheduler to refresh manager-owned widget data.
- Starter integrations:
  - Open-Meteo weather
  - RSS headlines
  - Quote feed
  - Google Calendar adapter stub

## Quick start

```bash
cp .env.example .env
docker compose up --build -d
docker compose ps
```

Then open:

- `http://localhost:8000/health`
- `http://localhost:8000/docs`

## LXC host notes

- Works fine when Docker is running inside your LXC container.
- If your LXC host has storage constraints, map `DATA_DIR` to a larger mount path in `.env`.
- Keep `./data` persisted so SQLite state survives container restarts.

## Example flow

1. Create a device via `POST /api/devices`.
2. Create/inspect templates and dashboards (`/api/templates`, `/api/dashboards`).
3. Assign dashboard to device via `POST /api/assignments`.
4. Firmware sends heartbeat with `X-Device-Token`.
5. Firmware pulls manifest from `/api/devices/{device_id}/manifest`.

## Project structure

- `app/main.py`: API entrypoint and routes
- `app/models.py`: SQLModel entities
- `app/services/scheduler.py`: refresh loop
- `app/services/integrations.py`: provider adapters
- `app/services/rendering.py`: manifest composition
- `docs/ARCHITECTURE.md`: system design notes
- `docs/FIRMWARE_CONTRACT.md`: device/backend JSON contract
- `docs/CODEX_PLATFORMIO_PROMPTS.md`: copy/paste prompts for PlatformIO firmware work

## Notes

- This is standalone by design and does not require Home Assistant.
- API boundaries are intentionally compatible with adding a Home Assistant bridge later.
- Google Calendar OAuth/token storage is the next implementation step beyond this starter.