from __future__ import annotations

import json
import uuid
from typing import Any

WEATHER_SOURCE_CHOICES = ["openmeteo", "wttr", "nws", "accuweather", "openweather", "weatherapi"]
NEWS_SOURCE_CHOICES = ["google", "reuters", "ap", "npr", "bbc", "custom", "newsapi", "nytimes"]

MAIN_SECTION_SIZE_OPTIONS = ["small", "medium", "large"]
REGION_WIDGET_SIZE_OPTIONS = ["quarter", "small", "half", "medium", "large", "full"]

MAIN_SECTION_SIZE_PRESETS: dict[str, dict[str, int]] = {
    "small": {"w": 3, "h": 2},
    "medium": {"w": 5, "h": 3},
    "large": {"w": 8, "h": 4},
}

REGION_SECTION_TEMPLATES: dict[str, dict[str, Any]] = {
    "header_summary": {
        "type": "header_summary",
        "title": "Header Summary",
        "default_size": "large",
        "integration": {"provider": "system_header", "config": {"show_ip": True, "show_temp": True}},
    },
    "forecast_summary": {
        "type": "forecast_summary",
        "title": "Forecast Summary",
        "default_size": "half",
        "integration": {"provider": "openmeteo", "config": {"zipcode": "63122"}},
    },
    "today_forecast": {
        "type": "today_forecast",
        "title": "Today's Forecast",
        "default_size": "half",
        "integration": {"provider": "openmeteo", "config": {"zipcode": "63122"}},
    },
    "today_date": {
        "type": "today_date",
        "title": "Today's Date",
        "default_size": "half",
        "integration": {"provider": "system_clock", "config": {"format": "EEE, MMM d"}},
    },
    "current_time": {
        "type": "current_time",
        "title": "Current Time",
        "default_size": "quarter",
        "integration": {"provider": "system_clock", "config": {"format": "h:mm a"}},
    },
    "current_temp": {
        "type": "current_temp",
        "title": "Current Temp",
        "default_size": "quarter",
        "integration": {"provider": "openmeteo", "config": {"zipcode": "63122"}},
    },
    "location": {
        "type": "location",
        "title": "Location",
        "default_size": "quarter",
        "integration": {"provider": "openmeteo", "config": {"zipcode": "63122"}},
    },
    "ip_address": {
        "type": "ip_address",
        "title": "IP Address",
        "default_size": "quarter",
        "integration": {"provider": "device_info", "config": {"ip_address": ""}},
    },
    "last_updated": {
        "type": "last_updated",
        "title": "Last Updated",
        "default_size": "quarter",
        "integration": {"provider": "system_clock", "config": {"format": "h:mm a"}},
    },
    "status_badge": {
        "type": "status_badge",
        "title": "Status Badge",
        "default_size": "quarter",
        "integration": {"provider": "manual", "config": {"label": "Online", "severity": "ok"}},
    },
    "humidity": {
        "type": "humidity",
        "title": "Humidity",
        "default_size": "quarter",
        "integration": {"provider": "openmeteo", "config": {"zipcode": "63122"}},
    },
    "wind": {
        "type": "wind",
        "title": "Wind",
        "default_size": "quarter",
        "integration": {"provider": "openmeteo", "config": {"zipcode": "63122"}},
    },
    "wifi_signal": {
        "type": "wifi_signal",
        "title": "Wi-Fi Signal",
        "default_size": "quarter",
        "integration": {"provider": "device_info", "config": {"rssi": -60}},
    },
    "battery": {
        "type": "battery",
        "title": "Battery",
        "default_size": "quarter",
        "integration": {"provider": "device_info", "config": {"percent": 82}},
    },
    "uptime": {
        "type": "uptime",
        "title": "Uptime",
        "default_size": "quarter",
        "integration": {"provider": "device_info", "config": {"uptime": "3d 11h"}},
    },
    "network_latency": {
        "type": "network_latency",
        "title": "Network Latency",
        "default_size": "quarter",
        "integration": {"provider": "device_info", "config": {"ms": 31}},
    },
    "stacked_text": {
        "type": "stacked_text",
        "title": "Stacked Text",
        "default_size": "half",
        "integration": {
            "provider": "manual",
            "config": {"line1": "Primary line", "line2": "Secondary line", "line3": "Tertiary line"},
        },
    },
}

SECTION_TEMPLATES: dict[str, dict[str, Any]] = {
    "weather": {
        "type": "weather",
        "title": "Weather",
        "layout": {"x": 0, "y": 1, "w": 5, "h": 4},
        "refresh": {"mode": "manager", "minutes": 15},
        "integration": {"provider": "openmeteo", "config": {"zipcode": "63122"}},
    },
    "headlines": {
        "type": "news",
        "title": "Headlines",
        "layout": {"x": 5, "y": 1, "w": 7, "h": 4},
        "refresh": {"mode": "manager", "minutes": 15},
        "integration": {"provider": "rss", "config": {"source": "google", "limit": 5}},
    },
    "quote": {
        "type": "quote",
        "title": "Quote of the Day",
        "layout": {"x": 0, "y": 6, "w": 12, "h": 1},
        "refresh": {"mode": "manager", "minutes": 720},
        "integration": {"provider": "quote", "config": {"source": "zenquotes", "text": "", "author": ""}},
    },
    "calendar_upcoming": {
        "type": "calendar",
        "title": "Upcoming Calendar",
        "layout": {"x": 0, "y": 5, "w": 12, "h": 1},
        "refresh": {"mode": "manager", "minutes": 15},
        "integration": {"provider": "google_calendar", "config": {"calendar_id": "primary", "credentials_ref": ""}},
    },
    "kpi_strip": {
        "type": "kpi_strip",
        "title": "KPI Strip",
        "layout": {"x": 0, "y": 1, "w": 12, "h": 2},
        "refresh": {"mode": "manager", "minutes": 10},
        "integration": {
            "provider": "manual",
            "config": {"items": [{"label": "Sales", "value": "102"}, {"label": "Tickets", "value": "17"}]},
        },
    },
    "status_panel": {
        "type": "status_panel",
        "title": "Status Panel",
        "layout": {"x": 0, "y": 3, "w": 6, "h": 3},
        "refresh": {"mode": "manager", "minutes": 10},
        "integration": {"provider": "manual", "config": {"title": "System", "status": "OK", "details": ["All services nominal"]}},
    },
    "todo_list": {
        "type": "todo_list",
        "title": "Task List",
        "layout": {"x": 6, "y": 3, "w": 6, "h": 3},
        "refresh": {"mode": "manager", "minutes": 30},
        "integration": {"provider": "manual", "config": {"items": ["Review headlines", "Check weather", "Sync device"]}},
    },
    "clock_panel": {
        "type": "clock_panel",
        "title": "Clock Panel",
        "layout": {"x": 0, "y": 1, "w": 4, "h": 2},
        "refresh": {"mode": "manager", "minutes": 1},
        "integration": {"provider": "system_clock", "config": {"timezone": "America/Chicago"}},
    },
    "alerts_feed": {
        "type": "alerts_feed",
        "title": "Alerts Feed",
        "layout": {"x": 4, "y": 1, "w": 8, "h": 2},
        "refresh": {"mode": "manager", "minutes": 10},
        "integration": {"provider": "rss", "config": {"source": "nws", "limit": 5}},
    },
    "system_health": {
        "type": "system_health",
        "title": "System Health",
        "layout": {"x": 0, "y": 3, "w": 6, "h": 3},
        "refresh": {"mode": "manager", "minutes": 5},
        "integration": {"provider": "device_info", "config": {"cpu": 18, "mem": 42, "disk": 56}},
    },
    "market_ticker": {
        "type": "market_ticker",
        "title": "Market Ticker",
        "layout": {"x": 6, "y": 3, "w": 6, "h": 2},
        "refresh": {"mode": "manager", "minutes": 15},
        "integration": {"provider": "manual", "config": {"symbols": ["SPY", "QQQ", "BTC"]}},
    },
    "notes_panel": {
        "type": "notes_panel",
        "title": "Notes Panel",
        "layout": {"x": 6, "y": 5, "w": 6, "h": 2},
        "refresh": {"mode": "manager", "minutes": 60},
        "integration": {"provider": "manual", "config": {"notes": ["Deploy at 8am", "Check panel battery"]}},
    },
}

DEFAULT_LAYOUT = {
    "orientation": "landscape",
    "grid": {"columns": 12, "rows": 8},
    "size": {"width": 600, "height": 448},
    "regions": {
        "title_bar": {
            "enabled": True,
            "height": 1,
            "widgets": [
                {
                    "id": "header_summary",
                    "template": "header_summary",
                    "type": "header_summary",
                    "title": "Header Summary",
                    "size": "large",
                    "layout": {"x": 0, "y": 0, "w": 7, "h": 1},
                    "integration": {"provider": "system_header", "config": {"show_ip": True, "show_temp": True}},
                },
                {
                    "id": "header_forecast",
                    "template": "forecast_summary",
                    "type": "forecast_summary",
                    "title": "Today's Forecast",
                    "size": "half",
                    "layout": {"x": 7, "y": 0, "w": 5, "h": 1},
                    "integration": {"provider": "openmeteo", "config": {"zipcode": "63122"}},
                },
            ],
        },
        "footer": {
            "enabled": True,
            "height": 1,
            "widgets": [
                {
                    "id": "footer_temp",
                    "template": "current_temp",
                    "type": "current_temp",
                    "title": "Current Temp",
                    "size": "quarter",
                    "layout": {"x": 0, "y": 0, "w": 3, "h": 1},
                    "integration": {"provider": "openmeteo", "config": {"zipcode": "63122"}},
                },
                {
                    "id": "footer_ip",
                    "template": "ip_address",
                    "type": "ip_address",
                    "title": "IP Address",
                    "size": "quarter",
                    "layout": {"x": 3, "y": 0, "w": 3, "h": 1},
                    "integration": {"provider": "device_info", "config": {"ip_address": ""}},
                },
                {
                    "id": "footer_status",
                    "template": "status_badge",
                    "type": "status_badge",
                    "title": "Status",
                    "size": "half",
                    "layout": {"x": 6, "y": 0, "w": 6, "h": 1},
                    "integration": {"provider": "manual", "config": {"label": "Online", "severity": "ok"}},
                },
            ],
        },
    },
}

DEFAULT_INTEGRATION_PRESETS = [
    {
        "name": "Open-Meteo (Default)",
        "slug": "weather-openmeteo",
        "category": "weather",
        "provider": "openmeteo",
        "description": "Free weather and forecast API used by the original firmware profile.",
        "auth_type": "none",
        "docs_url": "https://open-meteo.com/en/docs",
        "config_template": {"zipcode": "63122"},
        "is_default": True,
    },
    {
        "name": "wttr.in",
        "slug": "weather-wttr",
        "category": "weather",
        "provider": "wttr",
        "description": "Free weather JSON endpoint used as a fallback in the original firmware.",
        "auth_type": "none",
        "docs_url": "https://wttr.in/:help",
        "config_template": {"zipcode": "63122"},
        "is_default": True,
    },
    {
        "name": "NOAA/NWS",
        "slug": "weather-nws",
        "category": "weather",
        "provider": "nws",
        "description": "US weather and alert data source used in original firmware.",
        "auth_type": "none",
        "docs_url": "https://www.weather.gov/documentation/services-web-api",
        "config_template": {"zipcode": "63122"},
        "is_default": True,
    },
    {
        "name": "Google News RSS",
        "slug": "news-google-rss",
        "category": "news",
        "provider": "rss",
        "description": "Default headline feed from original firmware.",
        "auth_type": "none",
        "docs_url": "https://news.google.com/rss",
        "config_template": {"source": "google", "limit": 5},
        "is_default": True,
    },
    {
        "name": "Reuters World RSS",
        "slug": "news-reuters-rss",
        "category": "news",
        "provider": "rss",
        "description": "Alternative RSS news feed.",
        "auth_type": "none",
        "docs_url": "https://www.reutersagency.com/en/reutersbest/reuters-news-feeds/",
        "config_template": {"source": "reuters", "limit": 5},
        "is_default": True,
    },
    {
        "name": "ZenQuotes",
        "slug": "quote-zenquotes",
        "category": "quote",
        "provider": "quote",
        "description": "Default quote-of-day source in this starter manager.",
        "auth_type": "none",
        "docs_url": "https://zenquotes.io/",
        "config_template": {"source": "zenquotes"},
        "is_default": True,
    },
    {
        "name": "Google Calendar",
        "slug": "calendar-google",
        "category": "calendar",
        "provider": "google_calendar",
        "description": "OAuth-backed calendar integration template.",
        "auth_type": "oauth2",
        "docs_url": "https://developers.google.com/calendar/api",
        "config_template": {"calendar_id": "primary", "credentials_ref": ""},
        "is_default": True,
    },
    {
        "name": "AccuWeather",
        "slug": "weather-accuweather",
        "category": "weather",
        "provider": "accuweather",
        "description": "Commercial weather API option common in dashboard products.",
        "auth_type": "api_key",
        "docs_url": "https://developer.accuweather.com/apis",
        "config_template": {"api_key": "", "location_key": ""},
        "is_default": True,
    },
    {
        "name": "OpenWeather",
        "slug": "weather-openweather",
        "category": "weather",
        "provider": "openweather",
        "description": "Popular weather API option.",
        "auth_type": "api_key",
        "docs_url": "https://openweathermap.org/api",
        "config_template": {"api_key": "", "zipcode": "63122", "country": "US"},
        "is_default": True,
    },
    {
        "name": "WeatherAPI",
        "slug": "weather-weatherapi",
        "category": "weather",
        "provider": "weatherapi",
        "description": "Commercial weather provider used in signage and kiosk apps.",
        "auth_type": "api_key",
        "docs_url": "https://www.weatherapi.com/docs/",
        "config_template": {"api_key": "", "zipcode": "63122"},
        "is_default": True,
    },
    {
        "name": "NewsAPI",
        "slug": "news-newsapi",
        "category": "news",
        "provider": "newsapi",
        "description": "Structured news API alternative to RSS.",
        "auth_type": "api_key",
        "docs_url": "https://newsapi.org/docs",
        "config_template": {"api_key": "", "country": "us", "page_size": 5},
        "is_default": True,
    },
]


def clone_widget_template(name: str) -> dict[str, Any] | None:
    source = SECTION_TEMPLATES.get(name)
    if source is None:
        return None
    return json.loads(json.dumps(source))


def clone_section_template(name: str) -> dict[str, Any] | None:
    # Backward-compatible alias while the API migrates to widget terminology.
    return clone_widget_template(name)


def next_widget_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:6]}"


