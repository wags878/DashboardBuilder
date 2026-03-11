# Dashboard Builder Architecture (Starter)

This starter is a standalone, containerized Python dashboard manager designed for ESP32-C6 e-ink devices.

## Goals

- Keep dashboard design and fleet management in one web service.
- Keep rendering/data refresh resilient even when devices are temporarily disconnected from manager.
- Support multiple panel/screen types by preserving `panel_profile` and `platformio_env` metadata per device.
- Stay standalone first, but keep API boundaries that can map into Home Assistant later.

## Core Components

1. API Service (`FastAPI`)
- Manages templates, dashboards, devices, and assignments.
- Provides signed device manifest endpoint (`X-Device-Token`).

2. Data Refresh Worker (`APScheduler` in-process)
- Refreshes manager-owned widgets (weather, headlines, quote, calendar stub) on schedule.
- Stores snapshots in SQLite for fast device pulls.

3. Template + Widget Model
- Layout grid plus widget list.
- Widget-level refresh policy:
  - `manager`: backend fetches data and caches it.
  - `device`: device can fetch directly if it has internet and supports direct fetch.

4. Device Manifest Contract
- Includes target `panel_profile` and `platformio_env` for firmware profile compatibility.
- Includes widget data cache and refresh directives.

## Essentials for Dashboard Designer + Manager

1. Template registry
- Versioned templates (`slug`, `version`) so firmware-facing manifest shape stays stable.

2. Dashboard instance layer
- A dashboard is a template + widget integration bindings + timezone + refresh policy.

3. Device inventory + assignment
- Device has auth token, hardware profile metadata, and heartbeat state.
- Assignment ties one dashboard to one device with optional overrides.

4. Integration adapter boundary
- Provider-specific adapters (`openmeteo`, `rss`, `google_calendar`) hidden behind one fetch API.
- Lets you add providers without changing firmware contract.

5. Snapshot cache
- Prevents every device poll from calling third-party APIs directly.
- Supports stale-data fallback during provider/API outages.

6. Firmware contract layer
- Keep one stable JSON manifest schema consumed by all PlatformIO device profiles.

## Data Flow

1. Admin creates template/dashboard and assigns it to device.
2. Scheduler refreshes manager-owned widgets and stores snapshots.
3. Device sends heartbeat.
4. Device pulls manifest.
5. Device renders:
- manager mode widgets from snapshot payload
- device mode widgets using direct source hints (if supported)

## Home Assistant-Future Compatibility

- Keep device state and command model API-driven and topic-friendly.
- Maintain a normalized device model (`status`, `last_seen_at`, `metadata_json`).
- Later HA bridge can map:
  - Manager entities -> HA sensors
  - Dashboard commands -> HA services
  - Device availability -> HA availability topics

## What this starter intentionally leaves for next step

- OAuth credential vault and token refresh for Google Calendar.
- Browser UI for drag/drop dashboard design.
- Firmware-side manifest parser and renderer updates.
- Signed webhook/event model.