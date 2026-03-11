# Firmware Contract for ESP32-C6 E-Ink Devices

This contract is designed to fit your current PlatformIO firmware direction in:

- `C:\Github-AltPath\Seeedstudio-ESP-C6-with-EInk-breakout\ESP32-C6 with Eink Breakout\src\main.cpp`
- `C:\Github-AltPath\Seeedstudio-ESP-C6-with-EInk-breakout\ESP32-C6 with Eink Breakout\include\panel_profile.h`

## Device Registration (Manager Side)

Create device in manager:

- `POST /api/devices`

Store returned values on device:

- `device_id`
- `auth_token`
- `panel_profile`
- `platformio_env`

## Device Heartbeat

- `POST /api/devices/{device_id}/heartbeat`
- Header: `X-Device-Token: <auth_token>`

Payload example:

```json
{
  "firmware_version": "0.2.0",
  "ip_address": "192.168.1.88",
  "wifi_rssi": -67,
  "panel_profile": "solum_ed057tc6_baseline",
  "status": "online",
  "extra": {
    "heap_free": 132448,
    "uptime_seconds": 4812
  }
}
```

## Manifest Pull

- `GET /api/devices/{device_id}/manifest`
- Header: `X-Device-Token: <auth_token>`

Response shape:

```json
{
  "generated_at": "2026-03-11T18:15:00Z",
  "device_id": "...",
  "panel_profile": "solum_ed057tc6_baseline",
  "platformio_env": "seeed_xiao_esp32c6_solum_baseline_locked",
  "dashboard": {
    "id": "...",
    "name": "Starter Dashboard",
    "template_id": "...",
    "timezone": "America/Chicago",
    "refresh_defaults": {
      "minimum_minutes": 5
    }
  },
  "widgets": [
    {
      "id": "weather_main",
      "type": "weather",
      "title": "Weather",
      "layout": {"x": 0, "y": 3, "w": 5, "h": 3},
      "refresh": {"mode": "manager", "minutes": 15},
      "data": {
        "provider": "openmeteo",
        "status": "ok",
        "current": {"temp_f": 52.1}
      },
      "cache": {
        "fetched_at": "2026-03-11T18:10:00Z",
        "expires_at": "2026-03-11T18:25:00Z",
        "error": ""
      }
    }
  ]
}
```

## Refresh Modes

1. `manager`
- Backend owns polling and cache.
- Device only renders delivered payload.

2. `device`
- Device receives `data_source` hints and fetches data directly.
- Use this only where firmware-side parsing/fetch is stable and memory-safe.

## Recommended mapping to current firmware

Your current firmware already supports:

- independent periodic refresh loop logic
- weather/news/quote providers
- profile-specific panel behavior

Recommended adaptation path:

1. Add manager endpoint config fields to firmware settings.
2. Add manifest pull in loop with ETag/hash caching.
3. Convert current local dashboard data model into widget renderer map.
4. Keep existing local fallback providers as offline/degraded fallback mode.

## Security minimums

- Always require `X-Device-Token` on manifest/heartbeat.
- Rotate tokens via manager API when provisioning new devices.
- Avoid embedding third-party OAuth secrets in firmware.