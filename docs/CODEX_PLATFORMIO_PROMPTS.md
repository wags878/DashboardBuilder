# Codex Prompts for VSCode (PlatformIO Hardware Project)

Use these prompts directly in VSCode Codex when working in:

- `C:\Github-AltPath\Seeedstudio-ESP-C6-with-EInk-breakout\ESP32-C6 with Eink Breakout`

## 1) Baseline hardware bring-up

```text
Open platformio.ini and set default_envs to seeed_xiao_esp32c6_solum_baseline_locked. Build and upload to COM18. Then verify serial logs include EPD pins, panel profile id, Wi-Fi/AP setup complete, and HTTP server started. If upload fails, detect the correct COM port and retry.
```

## 2) Safe new panel profile creation

```text
Create a new PlatformIO environment by copying seeed_xiao_esp32c6_solum_baseline_locked and naming it seeed_xiao_esp32c6_<my_panel_name>. Only change EPD_MODEL_*, EPD_CS, EPD_DC, EPD_RST, EPD_BUSY, EPD_SPI_HZ, EPD_RST_MS, and EPD_PAGE_HEIGHT. Do not modify baseline locked env. Build it and summarize the exact changed flags.
```

## 3) Diagnose panel response quickly

```text
Build and upload the diag environment closest to this panel profile (src/epd_diag.cpp env). Capture serial output and summarize BUSY pin behavior and whether refresh loops are visible on panel. If no activity, try a no-BUSY variant and slower SPI.
```

## 4) Add manager API client settings to firmware UI

```text
In src/main.cpp, add persistent config fields and Settings UI inputs for dashboard manager URL, device_id, and device_token. Save them in Preferences, sanitize inputs, and expose read-only status on Home page. Keep role restrictions aligned with existing admin/service behavior.
```

## 5) Add heartbeat + manifest polling

```text
Implement a non-blocking loop task that posts heartbeat to /api/devices/{device_id}/heartbeat every 60 seconds and pulls /api/devices/{device_id}/manifest every 5 minutes using HTTPS. Use X-Device-Token header. If calls fail, keep rendering last cached dashboard.
```

## 6) Manifest-driven renderer scaffolding

```text
Refactor dashboard rendering in src/main.cpp so widget rendering reads from a manifest JSON structure instead of hardcoded weather/news sections. Start with weather_main, headlines, and quote widgets. Keep the existing local dashboard mode as fallback.
```

## 7) Add one-click manager compatibility test

```text
Add a debug endpoint in firmware web UI named “Test Manager Connection” that does a GET to /health on manager URL and prints status code, response time, and error text. Restrict this action to admin role.
```

## 8) Keep memory-safe JSON handling

```text
Review DynamicJsonDocument allocations used for weather/news APIs and propose right-sized capacities for manifest parsing on ESP32-C6. Reduce peak RAM usage and add serial heap diagnostics before/after network fetch and parse.
```

## 9) Provisioning flow for new board

```text
Implement a provisioning wizard in firmware: if manager URL/device token are missing, show Setup Needed on display and expose a web form under /config. After save, validate manager /health, then reboot.
```

## 10) Preserve future Home Assistant compatibility

```text
Keep MQTT state publishing intact while adding manager mode. Publish manifest sync state, last manager contact timestamp, and current dashboard id in MQTT state JSON without breaking existing keys.
```

## Recommended order

1. Prompt 1
2. Prompt 2 or 3 (depending on panel certainty)
3. Prompt 4
4. Prompt 5
5. Prompt 6
6. Prompt 7
7. Prompt 10