from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from apscheduler.schedulers.background import BackgroundScheduler
from sqlmodel import Session, select

from app.config import settings
from app.db import engine
from app.models import Dashboard, DataSnapshot
from app.services.integrations import fetch_widget_data

scheduler = BackgroundScheduler(timezone="UTC")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _is_due(snapshot: DataSnapshot | None, now: datetime) -> bool:
    if snapshot is None:
        return True
    if snapshot.expires_at is None:
        return True
    return snapshot.expires_at <= now


def _find_snapshot(session: Session, dashboard_id: str, widget_id: str) -> DataSnapshot | None:
    stmt = select(DataSnapshot).where(
        DataSnapshot.dashboard_id == dashboard_id,
        DataSnapshot.widget_id == widget_id,
    )
    return session.exec(stmt).first()


def _upsert_snapshot(
    session: Session,
    dashboard_id: str,
    widget_id: str,
    payload: dict[str, Any],
    expires_at: datetime,
    error: str,
) -> None:
    row = _find_snapshot(session, dashboard_id, widget_id)
    now = _utcnow()
    if row is None:
        row = DataSnapshot(
            dashboard_id=dashboard_id,
            widget_id=widget_id,
            payload=payload,
            fetched_at=now,
            expires_at=expires_at,
            error=error,
        )
        session.add(row)
        return

    row.payload = payload
    row.fetched_at = now
    row.expires_at = expires_at
    row.error = error
    session.add(row)


def refresh_dashboard_widgets(
    session: Session,
    dashboard: Dashboard,
    force: bool = False,
) -> tuple[list[str], list[str]]:
    refreshed: list[str] = []
    skipped: list[str] = []
    now = _utcnow()

    for widget in dashboard.widgets:
        widget_id = str(widget.get("id", "")).strip()
        if not widget_id:
            skipped.append("<missing-id>")
            continue

        refresh = widget.get("refresh", {}) if isinstance(widget.get("refresh"), dict) else {}
        mode = str(refresh.get("mode", "manager")).strip().lower() or "manager"
        if mode != "manager":
            skipped.append(widget_id)
            continue

        snapshot = _find_snapshot(session, dashboard.id, widget_id)
        if not force and not _is_due(snapshot, now):
            skipped.append(widget_id)
            continue

        payload, expires_at, error = fetch_widget_data(widget)
        _upsert_snapshot(session, dashboard.id, widget_id, payload, expires_at, error)
        refreshed.append(widget_id)

    dashboard.updated_at = _utcnow()
    session.add(dashboard)
    session.commit()
    return refreshed, skipped


def _scheduler_tick() -> None:
    with Session(engine) as session:
        dashboards = session.exec(select(Dashboard).where(Dashboard.enabled == True)).all()  # noqa: E712
        for dashboard in dashboards:
            refresh_dashboard_widgets(session, dashboard, force=False)


def start_scheduler() -> None:
    if scheduler.running:
        return
    scheduler.add_job(
        _scheduler_tick,
        trigger="interval",
        seconds=max(15, settings.scheduler_tick_seconds),
        id="dashboard-refresh-loop",
        replace_existing=True,
    )
    scheduler.start()


def stop_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)