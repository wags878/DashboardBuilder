from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from fastapi import Depends, FastAPI, Form, Header, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select
from starlette.middleware.sessions import SessionMiddleware

from app.config import settings
from app.db import create_db_and_tables, engine, get_session
from app.models import Dashboard, Device, DeviceAssignment, IntegrationPreset, Template
from app.schemas import (
    AssignmentCreate,
    DashboardCreate,
    DashboardPatch,
    DeviceCreate,
    DeviceHeartbeat,
    DeviceManifestResponse,
    ManualRefreshResponse,
    TemplateCreate,
)
from app.services.rendering import build_manifest
from app.services.scheduler import refresh_dashboard_widgets, start_scheduler, stop_scheduler
from app.ui_config import (
    DEFAULT_INTEGRATION_PRESETS,
    DEFAULT_LAYOUT,
    NEWS_SOURCE_CHOICES,
    SECTION_TEMPLATES,
    WEATHER_SOURCE_CHOICES,
    clone_section_template,
    next_widget_id,
)


templates = Jinja2Templates(directory="app/templates")

app = FastAPI(title=settings.app_name, version="0.2.0")
app.add_middleware(SessionMiddleware, secret_key=settings.session_secret)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _auth_redirect() -> RedirectResponse:
    return RedirectResponse(url="/login", status_code=302)


def _require_ui_auth(request: Request) -> RedirectResponse | None:
    if request.session.get("user"):
        return None
    return _auth_redirect()


def _render(request: Request, template_name: str, context: dict[str, Any]) -> HTMLResponse:
    base_context = {
        "request": request,
        "app_name": settings.app_name,
        "current_user": request.session.get("user"),
    }
    base_context.update(context)
    return templates.TemplateResponse(template_name, base_context)


def _default_layout_for_dashboard(dashboard: Dashboard, template: Template | None) -> dict[str, Any]:
    layout = (dashboard.refresh_defaults or {}).get("layout")
    if isinstance(layout, dict) and layout:
        return layout
    if template and isinstance(template.layout, dict) and template.layout:
        return template.layout
    return DEFAULT_LAYOUT


def _seed_defaults(session: Session) -> None:
    template = session.exec(select(Template).where(Template.slug == "firmware-base-layout-v1")).first()
    if template is None:
        template = Template(
            name="Firmware Base Layout",
            slug="firmware-base-layout-v1",
            description="Base layout derived from the original ESP32-C6 dashboard sections.",
            version="1.0.0",
            layout=DEFAULT_LAYOUT,
            default_widgets=[
                {**SECTION_TEMPLATES["weather"], "id": "weather_main"},
                {**SECTION_TEMPLATES["headlines"], "id": "headlines_main"},
                {**SECTION_TEMPLATES["quote"], "id": "quote_daily"},
            ],
        )
        session.add(template)
        session.commit()
        session.refresh(template)

    existing_dashboard = session.exec(select(Dashboard).where(Dashboard.name == "Starter Dashboard")).first()
    if existing_dashboard is None:
        dashboard = Dashboard(
            name="Starter Dashboard",
            template_id=template.id,
            timezone="America/Chicago",
            widgets=template.default_widgets,
            refresh_defaults={"minimum_minutes": 5, "layout": DEFAULT_LAYOUT},
            enabled=True,
        )
        session.add(dashboard)
        session.commit()

    for preset in DEFAULT_INTEGRATION_PRESETS:
        exists = session.exec(select(IntegrationPreset).where(IntegrationPreset.slug == preset["slug"])).first()
        if exists is None:
            session.add(IntegrationPreset(**preset))
    session.commit()


@app.on_event("startup")
def on_startup() -> None:
    create_db_and_tables()
    with Session(engine) as session:
        _seed_defaults(session)
    start_scheduler()


@app.on_event("shutdown")
def on_shutdown() -> None:
    stop_scheduler()


@app.get("/", response_class=HTMLResponse)
def home(request: Request) -> RedirectResponse:
    if request.session.get("user"):
        return RedirectResponse(url="/designer", status_code=302)
    return RedirectResponse(url="/login", status_code=302)


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request) -> HTMLResponse | RedirectResponse:
    if request.session.get("user"):
        return RedirectResponse(url="/designer", status_code=302)
    return _render(request, "login.html", {"error": ""})


@app.post("/login", response_class=HTMLResponse)
def login_submit(request: Request, username: str = Form(...), password: str = Form(...)) -> HTMLResponse | RedirectResponse:
    if username == settings.admin_username and password == settings.admin_password:
        request.session["user"] = username
        return RedirectResponse(url="/designer", status_code=302)
    return _render(request, "login.html", {"error": "Invalid username or password."})


@app.post("/logout")
def logout(request: Request) -> RedirectResponse:
    request.session.clear()
    return RedirectResponse(url="/login", status_code=302)
