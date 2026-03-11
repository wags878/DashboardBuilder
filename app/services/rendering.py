from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlmodel import Session, select

from app.models import Dashboard, DataSnapshot, Device, DeviceAssignment
from app.services.integrations import direct_source_descriptor


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _snapshot_map(session: Session, dashboard_id: str) -> dict[str, DataSnapshot]:
    rows = session.exec(select(DataSnapshot).where(DataSnapshot.dashboard_id == dashboard_id)).all()
    return {row.widget_id: row for row in rows}


def build_manifest(
    session: Session,
    device: Device,
    assignment: DeviceAssignment,
    dashboard: Dashboard,
) -> dict[str, Any]:
    snapshots = _snapshot_map(session, dashboard.id)
    rendered_widgets: list[dict[str, Any]] = []

    for widget in dashboard.widgets:
        widget_id = str(widget.get("id", "")).strip()
        if not widget_id:
            continue

        refresh = widget.get("refresh", {}) if isinstance(widget.get("refresh"), dict) else {}
        refresh_mode = str(refresh.get("mode", "manager")).strip().lower() or "manager"
        if refresh_mode not in {"manager", "device"}:
            refresh_mode = "manager"

        widget_out: dict[str, Any] = {
            "id": widget_id,
            "type": widget.get("type", "unknown"),
            "title": widget.get("title", ""),
            "layout": widget.get("layout", {}),
            "refresh": {
                "mode": refresh_mode,
                "minutes": int(refresh.get("minutes", 15)),
            },
        }

        snap = snapshots.get(widget_id)
        if snap is not None:
            widget_out["data"] = snap.payload
            widget_out["cache"] = {
                "fetched_at": snap.fetched_at.isoformat(),
                "expires_at": snap.expires_at.isoformat() if snap.expires_at else None,
                "error": snap.error,
            }

        if refresh_mode == "device" and device.supports_direct_fetch:
            widget_out["data_source"] = direct_source_descriptor(widget)

        rendered_widgets.append(widget_out)

    manifest = {
        "generated_at": _utcnow().isoformat(),
        "device_id": device.id,
        "panel_profile": assignment.overrides.get("panel_profile", device.panel_profile),
        "platformio_env": assignment.overrides.get("platformio_env", device.platformio_env),
        "dashboard": {
            "id": dashboard.id,
            "name": dashboard.name,
            "template_id": dashboard.template_id,
            "timezone": dashboard.timezone,
            "refresh_defaults": dashboard.refresh_defaults,
        },
        "widgets": rendered_widgets,
    }
    return manifest