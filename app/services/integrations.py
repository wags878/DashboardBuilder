from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from xml.etree import ElementTree

import httpx

NEWS_FEEDS = {
    "google": "https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en",
    "reuters": "https://feeds.reuters.com/Reuters/worldNews",
    "ap": "https://feeds.apnews.com/apnews/topnews",
    "npr": "https://feeds.npr.org/1001/rss.xml",
    "bbc": "https://feeds.bbci.co.uk/news/world/rss.xml",
}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def widget_refresh_minutes(widget: dict[str, Any]) -> int:
    refresh = widget.get("refresh", {})
    try:
        return max(5, int(refresh.get("minutes", 15)))
    except (TypeError, ValueError):
        return 15


def _client() -> httpx.Client:
    return httpx.Client(timeout=12.0, follow_redirects=True)


def _resolve_zip(zipcode: str) -> tuple[float, float, str] | None:
    params = {
        "name": zipcode,
        "count": 1,
        "language": "en",
        "format": "json",
    }
    with _client() as client:
        response = client.get("https://geocoding-api.open-meteo.com/v1/search", params=params)
        response.raise_for_status()
        body = response.json()
    results = body.get("results") or []
    if not results:
        return None
    top = results[0]
    return float(top["latitude"]), float(top["longitude"]), top.get("name", f"ZIP {zipcode}")


def _fetch_weather_openmeteo(config: dict[str, Any]) -> dict[str, Any]:
    zipcode = str(config.get("zipcode", "63122"))
    location = _resolve_zip(zipcode)
    if not location:
        return {
            "provider": "openmeteo",
            "status": "error",
            "message": f"Could not resolve zipcode {zipcode}.",
        }

    latitude, longitude, location_name = location
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current": "temperature_2m,weather_code,time",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min",
        "forecast_days": 7,
        "temperature_unit": "fahrenheit",
        "timezone": "auto",
    }
    with _client() as client:
        response = client.get("https://api.open-meteo.com/v1/forecast", params=params)
        response.raise_for_status()
        body = response.json()

    current = body.get("current", {})
    daily = body.get("daily", {})
    times = daily.get("time", [])
    highs = daily.get("temperature_2m_max", [])
    lows = daily.get("temperature_2m_min", [])
    codes = daily.get("weather_code", [])

    forecast = []
    for day, hi, lo, code in zip(times[:5], highs[:5], lows[:5], codes[:5]):
        forecast.append(
            {
                "date": day,
                "high_f": hi,
                "low_f": lo,
                "weather_code": code,
            }
        )

    return {
        "provider": "openmeteo",
        "status": "ok",
        "zipcode": zipcode,
        "location": location_name,
        "current": {
            "temp_f": current.get("temperature_2m"),
            "weather_code": current.get("weather_code"),
            "time": current.get("time"),
        },
        "forecast": forecast,
    }


def _feed_url(config: dict[str, Any]) -> str:
    source = str(config.get("source", "google")).strip().lower()
    if source == "custom":
        custom = str(config.get("url", "")).strip()
        if custom.startswith("http://") or custom.startswith("https://"):
            return custom
    return NEWS_FEEDS.get(source, NEWS_FEEDS["google"])


def _fetch_news_rss(config: dict[str, Any]) -> dict[str, Any]:
    limit = int(config.get("limit", 5))
    limit = max(1, min(limit, 10))
    url = _feed_url(config)

    with _client() as client:
        response = client.get(url)
        response.raise_for_status()
        xml_text = response.text

    root = ElementTree.fromstring(xml_text)
    items: list[dict[str, Any]] = []
    for item in root.findall(".//item")[:limit]:
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        if title:
            items.append({"title": title, "link": link})

    return {
        "provider": "rss",
        "status": "ok",
        "source_url": url,
        "headlines": items,
    }


def _fetch_quote(config: dict[str, Any]) -> dict[str, Any]:
    custom_quote = str(config.get("text", "")).strip()
    if custom_quote:
        return {
            "provider": "quote",
            "status": "ok",
            "quote": custom_quote,
            "author": str(config.get("author", "Custom")).strip() or "Custom",
        }

    with _client() as client:
        response = client.get("https://zenquotes.io/api/random")
        response.raise_for_status()
        body = response.json()

    quote = body[0] if body else {}
    return {
        "provider": "quote",
        "status": "ok",
        "quote": quote.get("q", "Stay focused. Build one solid step at a time."),
        "author": quote.get("a", "Fallback"),
    }


def _fetch_google_calendar(config: dict[str, Any]) -> dict[str, Any]:
    credentials_ref = str(config.get("credentials_ref", "")).strip()
    if not credentials_ref:
        return {
            "provider": "google_calendar",
            "status": "not_configured",
            "message": "Set credentials_ref to enable Google Calendar sync.",
            "events": [],
        }

    # Stub output until OAuth and token storage are wired in.
    return {
        "provider": "google_calendar",
        "status": "stub",
        "calendar_id": str(config.get("calendar_id", "primary")),
        "message": "OAuth flow not yet implemented in this starter.",
        "events": [
            {
                "title": "Example Event",
                "start": "2026-03-11T09:00:00-06:00",
                "end": "2026-03-11T09:30:00-06:00",
            }
        ],
    }


def direct_source_descriptor(widget: dict[str, Any]) -> dict[str, Any]:
    integration = widget.get("integration", {})
    provider = str(integration.get("provider", "")).strip().lower()
    config = integration.get("config", {}) if isinstance(integration.get("config"), dict) else {}

    if provider == "openmeteo":
        zipcode = str(config.get("zipcode", "63122")).strip() or "63122"
        return {
            "provider": "openmeteo",
            "fetch_hint": "Device should geocode zipcode then fetch open-meteo forecast.",
            "config": {"zipcode": zipcode},
        }
    if provider == "rss":
        return {
            "provider": "rss",
            "fetch_hint": "Device should fetch RSS feed and parse <item><title> entries.",
            "config": {"url": _feed_url(config), "limit": max(1, min(int(config.get("limit", 5)), 10))},
        }
    if provider == "quote":
        return {
            "provider": "quote",
            "fetch_hint": "Use manager mode for quote widgets unless fixed custom quote.",
            "config": config,
        }
    if provider == "google_calendar":
        return {
            "provider": "google_calendar",
            "fetch_hint": "Prefer manager mode due to OAuth complexity.",
            "config": {
                "calendar_id": str(config.get("calendar_id", "primary")),
                "credentials_ref": str(config.get("credentials_ref", "")),
            },
        }
    return {"provider": provider or "unknown", "config": config}


def fetch_widget_data(widget: dict[str, Any]) -> tuple[dict[str, Any], datetime, str]:
    provider = (
        str(widget.get("integration", {}).get("provider", "")).strip().lower()
        if isinstance(widget.get("integration"), dict)
        else ""
    )
    config = widget.get("integration", {}).get("config", {})
    if not isinstance(config, dict):
        config = {}

    minutes = widget_refresh_minutes(widget)
    expires_at = utcnow() + timedelta(minutes=minutes)

    try:
        if provider == "openmeteo":
            return _fetch_weather_openmeteo(config), expires_at, ""
        if provider == "rss":
            return _fetch_news_rss(config), expires_at, ""
        if provider == "quote":
            return _fetch_quote(config), expires_at, ""
        if provider == "google_calendar":
            return _fetch_google_calendar(config), expires_at, ""
        return (
            {
                "provider": provider or "unknown",
                "status": "error",
                "message": "Unknown widget integration provider.",
            },
            expires_at,
            "unknown_provider",
        )
    except Exception as exc:  # pragma: no cover - network and remote API failure branch
        return (
            {
                "provider": provider or "unknown",
                "status": "error",
                "message": str(exc),
            },
            expires_at,
            str(exc),
        )