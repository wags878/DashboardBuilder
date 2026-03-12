from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import Depends, FastAPI, Form, Header, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select
from starlette.middleware.sessions import SessionMiddleware

from app.config import settings
from app.db import create_db_and_tables, engine, get_session
from app.models import Dashboard, DataSnapshot, Device, DeviceAssignment, FirmwareImage, IntegrationPreset, Template
from app.schemas import (
    AssignmentCreate,
    DashboardCreate,
    DashboardPatch,
    DeviceCreate,
    DeviceHeartbeat,
    DeviceManifestResponse,
    ManualRefreshResponse,
    ProvisionClaimRequest,
    TemplateCreate,
)

from app.services.rendering import build_manifest
from app.services.scheduler import refresh_dashboard_widgets, start_scheduler, stop_scheduler
from app.ui_config import (
    DEFAULT_INTEGRATION_PRESETS,
    DEFAULT_LAYOUT,
    MAIN_SECTION_SIZE_OPTIONS,
    MAIN_SECTION_SIZE_PRESETS,
    NEWS_SOURCE_CHOICES,
    REGION_SECTION_TEMPLATES,
    REGION_WIDGET_SIZE_OPTIONS,
    SECTION_TEMPLATES,
    WEATHER_SOURCE_CHOICES,
    clone_widget_template,
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


def _safe_int(value: Any, fallback: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def _normalized_main_section_size(size_candidate: Any) -> str:
    size = str(size_candidate or "medium").strip().lower()
    return size if size in MAIN_SECTION_SIZE_OPTIONS else "medium"


def _normalized_region_size(size_candidate: Any) -> str:
    size = str(size_candidate or "half").strip().lower()
    return size if size in REGION_WIDGET_SIZE_OPTIONS else "half"


def _region_span_for_size(columns: int, size: str) -> int:
    cols = max(1, columns)
    if size == "quarter":
        return max(1, min(cols, max(1, cols // 4)))
    if size == "small":
        return max(1, min(cols, max(1, cols // 6)))
    if size == "half":
        return max(1, min(cols, max(2, cols // 2)))
    if size == "medium":
        return max(1, min(cols, max(2, cols // 3)))
    if size == "large":
        return max(1, min(cols, max(3, (2 * cols) // 3)))
    if size == "full":
        return cols
    return max(1, min(cols, max(2, cols // 3)))


def _sanitize_region_widgets(raw_widgets: Any, columns: int, rows: int, prefix: str) -> list[dict[str, Any]]:
    clean: list[dict[str, Any]] = []
    if not isinstance(raw_widgets, list):
        return clean

    cols = max(1, min(24, columns))
    region_rows = max(1, min(4, rows))

    for idx, item in enumerate(raw_widgets):
        if not isinstance(item, dict):
            continue

        size = _normalized_region_size(item.get("size"))
        template_key = str(item.get("template", item.get("type", ""))).strip().lower()
        template = REGION_SECTION_TEMPLATES.get(template_key, {})
        layout = item.get("layout", {}) if isinstance(item.get("layout"), dict) else {}

        base_w = _region_span_for_size(cols, size)
        w = max(1, min(cols, _safe_int(layout.get("w"), base_w)))
        x = max(0, min(cols - w, _safe_int(layout.get("x"), 0)))
        h = max(1, min(region_rows, _safe_int(layout.get("h"), 1)))
        y = max(0, min(region_rows - h, _safe_int(layout.get("y"), 0)))

        integration = item.get("integration", {}) if isinstance(item.get("integration"), dict) else {}
        provider = str(integration.get("provider") or template.get("integration", {}).get("provider", "")).strip()
        config = integration.get("config", {}) if isinstance(integration.get("config"), dict) else {}
        if not config and isinstance(template.get("integration"), dict):
            template_cfg = template["integration"].get("config", {})
            config = template_cfg if isinstance(template_cfg, dict) else {}

        title = str(item.get("title") or template.get("title") or "Widget").strip()

        clean.append(
            {
                "id": str(item.get("id") or "").strip() or next_widget_id(f"{prefix}{idx}"),
                "template": template_key or str(item.get("type", "custom")).strip().lower() or "custom",
                "type": str(item.get("type") or template.get("type") or template_key or "custom").strip() or "custom",
                "title": title,
                "size": size,
                "layout": {"x": x, "y": y, "w": w, "h": h},
                "integration": {
                    "provider": provider,
                    "config": config,
                },
            }
        )

    return clean


def _apply_main_section_size(widget: dict[str, Any], size_candidate: Any, columns: int, rows: int) -> dict[str, Any]:
    size = _normalized_main_section_size(size_candidate)
    preset = MAIN_SECTION_SIZE_PRESETS.get(size, MAIN_SECTION_SIZE_PRESETS["medium"])

    layout = widget.get("layout", {}) if isinstance(widget.get("layout"), dict) else {}
    x = _safe_int(layout.get("x"), 0)
    y = _safe_int(layout.get("y"), 0)

    cols = max(1, min(24, columns))
    grid_rows = max(1, min(24, rows))

    w = max(1, min(cols, _safe_int(preset.get("w"), 5)))
    h = max(1, min(grid_rows, _safe_int(preset.get("h"), 3)))
    x = max(0, min(cols - w, x))
    y = max(0, min(grid_rows - h, y))

    widget["layout"] = {"x": x, "y": y, "w": w, "h": h}

    integration = widget.get("integration", {}) if isinstance(widget.get("integration"), dict) else {}
    config = integration.get("config", {}) if isinstance(integration.get("config"), dict) else {}
    config["display_size"] = size
    config["density"] = {"small": "compact", "medium": "balanced", "large": "expanded"}.get(size, "balanced")
    integration["config"] = config
    widget["integration"] = integration
    return widget

def _normalized_layout(layout_candidate: dict[str, Any] | None) -> dict[str, Any]:
    layout = json.loads(json.dumps(DEFAULT_LAYOUT))
    if not isinstance(layout_candidate, dict):
        return layout

    orientation = layout_candidate.get("orientation")
    if isinstance(orientation, str) and orientation.strip():
        layout["orientation"] = orientation.strip().lower()

    grid = layout_candidate.get("grid")
    if isinstance(grid, dict):
        cols = grid.get("columns")
        rows = grid.get("rows")
        if isinstance(cols, int):
            layout["grid"]["columns"] = max(1, min(24, cols))
        if isinstance(rows, int):
            layout["grid"]["rows"] = max(1, min(24, rows))

    size = layout_candidate.get("size")
    if isinstance(size, dict):
        width = size.get("width")
        height = size.get("height")
        if isinstance(width, int) and width > 0:
            layout["size"]["width"] = width
        if isinstance(height, int) and height > 0:
            layout["size"]["height"] = height

    regions = layout_candidate.get("regions")
    if isinstance(regions, dict):
        title = regions.get("title_bar")
        footer = regions.get("footer")

        if isinstance(title, dict):
            if isinstance(title.get("enabled"), bool):
                layout["regions"]["title_bar"]["enabled"] = title["enabled"]
            if isinstance(title.get("height"), int):
                layout["regions"]["title_bar"]["height"] = max(1, min(4, title["height"]))
            if isinstance(title.get("widgets"), list):
                layout["regions"]["title_bar"]["widgets"] = _sanitize_region_widgets(
                    title.get("widgets"),
                    layout["grid"]["columns"],
                    layout["regions"]["title_bar"]["height"],
                    "header",
                )

        if isinstance(footer, dict):
            if isinstance(footer.get("enabled"), bool):
                layout["regions"]["footer"]["enabled"] = footer["enabled"]
            if isinstance(footer.get("height"), int):
                layout["regions"]["footer"]["height"] = max(1, min(4, footer["height"]))
            if isinstance(footer.get("widgets"), list):
                layout["regions"]["footer"]["widgets"] = _sanitize_region_widgets(
                    footer.get("widgets"),
                    layout["grid"]["columns"],
                    layout["regions"]["footer"]["height"],
                    "footer",
                )

    return layout


def _default_layout_for_dashboard(dashboard: Dashboard, template: Template | None) -> dict[str, Any]:
    layout = (dashboard.refresh_defaults or {}).get("layout")
    if isinstance(layout, dict) and layout:
        return _normalized_layout(layout)
    if template and isinstance(template.layout, dict) and template.layout:
        return _normalized_layout(template.layout)
    return _normalized_layout(None)


def _seed_defaults(session: Session) -> None:
    template = session.exec(select(Template).where(Template.slug == "firmware-base-layout-v1")).first()
    if template is None:
        template = Template(
            name="Firmware Base Layout",
            slug="firmware-base-layout-v1",
            description="Base layout derived from the original ESP32-C6 dashboard widgets.",
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
    else:
        normalized_template = _normalized_layout(template.layout if isinstance(template.layout, dict) else None)
        template_title_rows = int(normalized_template.get("regions", {}).get("title_bar", {}).get("height", 1))
        footer_widgets = normalized_template.get("regions", {}).get("footer", {}).get("widgets", [])
        has_ip_footer = isinstance(footer_widgets, list) and any(
            str(w.get("template") or w.get("type") or "").strip().lower() == "ip_address" for w in footer_widgets if isinstance(w, dict)
        )

        if template_title_rows != 1 or not has_ip_footer:
            template.layout = _normalized_layout(DEFAULT_LAYOUT)
            template.updated_at = _utcnow()
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
    else:
        starter_defaults = dict(existing_dashboard.refresh_defaults or {})
        starter_layout = _normalized_layout(starter_defaults.get("layout") if isinstance(starter_defaults.get("layout"), dict) else None)
        starter_title_rows = int(starter_layout.get("regions", {}).get("title_bar", {}).get("height", 1))
        starter_footer_widgets = starter_layout.get("regions", {}).get("footer", {}).get("widgets", [])
        starter_has_ip_footer = isinstance(starter_footer_widgets, list) and any(
            str(w.get("template") or w.get("type") or "").strip().lower() == "ip_address"
            for w in starter_footer_widgets
            if isinstance(w, dict)
        )

        if starter_title_rows != 1 or not starter_has_ip_footer:
            starter_defaults["layout"] = _normalized_layout(DEFAULT_LAYOUT)
            existing_dashboard.refresh_defaults = starter_defaults
            existing_dashboard.updated_at = _utcnow()
            session.add(existing_dashboard)
            session.commit()

    for preset in DEFAULT_INTEGRATION_PRESETS:
        exists = session.exec(select(IntegrationPreset).where(IntegrationPreset.slug == preset["slug"])).first()
        if exists is None:
            session.add(IntegrationPreset(**preset))

    firmware_defaults = [
        {
            "name": "Dashboard Firmware (Baseline)",
            "slug": "fw-esp32c6-solum-baseline",
            "board": "seeed_xiao_esp32c6",
            "panel_profile": "solum_ed057tc6_baseline",
            "platformio_env": "seeed_xiao_esp32c6_solum_baseline_locked",
            "version": "0.1.0",
            "binary_url": "",
            "notes": "Set binary URL after CI build artifact is available.",
            "is_default": True,
            "active": True,
        }
    ]
    for fw in firmware_defaults:
        fw_exists = session.exec(select(FirmwareImage).where(FirmwareImage.slug == fw["slug"])).first()
        if fw_exists is None:
            session.add(FirmwareImage(**fw))

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
def login_page(request: Request) -> Response:
    if request.session.get("user"):
        return RedirectResponse(url="/designer", status_code=302)
    return _render(request, "login.html", {"error": ""})


@app.post("/login", response_class=HTMLResponse)
def login_submit(request: Request, username: str = Form(...), password: str = Form(...)) -> Response:
    if username == settings.admin_username and password == settings.admin_password:
        request.session["user"] = username
        return RedirectResponse(url="/designer", status_code=302)
    return _render(request, "login.html", {"error": "Invalid username or password."})


@app.post("/logout")
def logout(request: Request) -> RedirectResponse:
    request.session.clear()
    return RedirectResponse(url="/login", status_code=302)

@app.get("/designer", response_class=HTMLResponse)
def designer_page(
    request: Request,
    dashboard_id: str | None = Query(default=None),
    session: Session = Depends(get_session),
 ) -> Response:
    auth = _require_ui_auth(request)
    if auth:
        return auth

    dashboards = session.exec(select(Dashboard)).all()
    template_rows = session.exec(select(Template)).all()

    if not dashboards:
        return _render(
            request,
            "designer.html",
            {
                "active_tab": "designer",
                "dashboards": [],
                "selected_dashboard": None,
                "layout_config": _normalized_layout(DEFAULT_LAYOUT),
                "widgets_json": "[]",
                "header_widgets_json": "[]",
                "footer_widgets_json": "[]",
                "section_templates": SECTION_TEMPLATES,
                "region_section_templates": REGION_SECTION_TEMPLATES,
                "main_section_size_options": MAIN_SECTION_SIZE_OPTIONS,
            "region_widget_size_options": REGION_WIDGET_SIZE_OPTIONS,
                "weather_source_choices": WEATHER_SOURCE_CHOICES,
                "news_source_choices": NEWS_SOURCE_CHOICES,
                "templates": template_rows,
                "message": "No dashboards yet. Create one from a preset.",
            },
        )

    selected = next((d for d in dashboards if d.id == dashboard_id), dashboards[0]) if dashboard_id else dashboards[0]
    selected_template = session.get(Template, selected.template_id)
    layout_config = _default_layout_for_dashboard(selected, selected_template)

    return _render(
        request,
        "designer.html",
        {
            "active_tab": "designer",
            "dashboards": dashboards,
            "selected_dashboard": selected,
            "layout_config": layout_config,
            "widgets_json": json.dumps(selected.widgets),
            "header_widgets_json": json.dumps(layout_config.get("regions", {}).get("title_bar", {}).get("widgets", [])),
            "footer_widgets_json": json.dumps(layout_config.get("regions", {}).get("footer", {}).get("widgets", [])),
            "section_templates": SECTION_TEMPLATES,
            "region_section_templates": REGION_SECTION_TEMPLATES,
            "main_section_size_options": MAIN_SECTION_SIZE_OPTIONS,
            "region_widget_size_options": REGION_WIDGET_SIZE_OPTIONS,
            "weather_source_choices": WEATHER_SOURCE_CHOICES,
            "news_source_choices": NEWS_SOURCE_CHOICES,
            "templates": template_rows,
            "message": request.query_params.get("msg", ""),
        },
    )


@app.post("/designer/dashboard-create")
def designer_dashboard_create(
    request: Request,
    session: Session = Depends(get_session),
    name: str = Form(...),
    template_id: str = Form(...),
    timezone: str = Form("America/Chicago"),
) -> RedirectResponse:
    auth = _require_ui_auth(request)
    if auth:
        return auth

    template = session.get(Template, template_id)
    if template is None:
        return RedirectResponse(url="/designer?msg=Template+not+found", status_code=302)

    dashboard = Dashboard(
        name=name.strip() or "New Dashboard",
        template_id=template.id,
        timezone=timezone.strip() or "America/Chicago",
        widgets=template.default_widgets,
        refresh_defaults={"minimum_minutes": 5, "layout": template.layout or DEFAULT_LAYOUT},
        enabled=True,
    )
    session.add(dashboard)
    session.commit()
    return RedirectResponse(url=f"/designer?dashboard_id={dashboard.id}&msg=Dashboard+created", status_code=302)


@app.post("/designer/add-section")
@app.post("/designer/add-widget")
def designer_add_widget(
    request: Request,
    session: Session = Depends(get_session),
    dashboard_id: str = Form(...),
    section_template: str = Form(...),
    template_size: str = Form("medium"),
) -> RedirectResponse:
    auth = _require_ui_auth(request)
    if auth:
        return auth

    dashboard = session.get(Dashboard, dashboard_id)
    if dashboard is None:
        return RedirectResponse(url="/designer?msg=Dashboard+not+found", status_code=302)

    source = clone_widget_template(section_template)
    if source is None:
        return RedirectResponse(url=f"/designer?dashboard_id={dashboard_id}&msg=Unknown+widget", status_code=302)

    source["id"] = next_widget_id(section_template)
    layout_cfg = _default_layout_for_dashboard(dashboard, session.get(Template, dashboard.template_id))
    cols = int(layout_cfg.get("grid", {}).get("columns", 12))
    rows = int(layout_cfg.get("grid", {}).get("rows", 8))
    source = _apply_main_section_size(source, template_size, cols, rows)
    dashboard.widgets = [*dashboard.widgets, source]
    dashboard.updated_at = _utcnow()
    session.add(dashboard)
    session.commit()
    return RedirectResponse(url=f"/designer?dashboard_id={dashboard.id}&msg=Widget+added", status_code=302)


@app.post("/designer/save")
def designer_save(
    request: Request,
    session: Session = Depends(get_session),
    dashboard_id: str = Form(...),
    timezone: str = Form("America/Chicago"),
    title_enabled: str | None = Form(default=None),
    title_height: int = Form(1),
    footer_enabled: str | None = Form(default=None),
    footer_height: int = Form(1),
    grid_columns: int = Form(12),
    grid_rows: int = Form(8),
    widgets_json: str = Form("[]"),
    header_widgets_json: str = Form("[]"),
    footer_widgets_json: str = Form("[]"),
) -> RedirectResponse:
    auth = _require_ui_auth(request)
    if auth:
        return auth

    dashboard = session.get(Dashboard, dashboard_id)
    if dashboard is None:
        return RedirectResponse(url="/designer?msg=Dashboard+not+found", status_code=302)

    try:
        widgets = json.loads(widgets_json)
        if not isinstance(widgets, list):
            raise ValueError("widgets_json not list")
    except Exception:
        return RedirectResponse(url=f"/designer?dashboard_id={dashboard_id}&msg=Invalid+widget+JSON", status_code=302)

    try:
        header_widgets_raw = json.loads(header_widgets_json)
        if not isinstance(header_widgets_raw, list):
            raise ValueError("header_widgets_json not list")
        footer_widgets_raw = json.loads(footer_widgets_json)
        if not isinstance(footer_widgets_raw, list):
            raise ValueError("footer_widgets_json not list")
    except Exception:
        return RedirectResponse(url=f"/designer?dashboard_id={dashboard_id}&msg=Invalid+header/footer+JSON", status_code=302)
    clean_widgets: list[dict[str, Any]] = []
    for idx, item in enumerate(widgets):
        if not isinstance(item, dict):
            continue
        layout = item.get("layout", {}) if isinstance(item.get("layout"), dict) else {}
        refresh = item.get("refresh", {}) if isinstance(item.get("refresh"), dict) else {}
        integration = item.get("integration", {}) if isinstance(item.get("integration"), dict) else {}
        clean_widgets.append(
            {
                "id": str(item.get("id", "")).strip() or next_widget_id(f"widget{idx}"),
                "type": str(item.get("type", "custom")).strip() or "custom",
                "title": str(item.get("title", "")).strip() or "Widget",
                "layout": {
                    "x": max(0, int(layout.get("x", 0))),
                    "y": max(0, int(layout.get("y", 0))),
                    "w": max(1, int(layout.get("w", 1))),
                    "h": max(1, int(layout.get("h", 1))),
                },
                "refresh": {
                    "mode": "device" if str(refresh.get("mode", "manager")).strip().lower() == "device" else "manager",
                    "minutes": max(5, int(refresh.get("minutes", 15))),
                },
                "integration": {
                    "provider": str(integration.get("provider", "")).strip(),
                    "config": integration.get("config", {}) if isinstance(integration.get("config"), dict) else {},
                },
            }
        )

    cols = max(1, min(24, int(grid_columns)))
    rows = max(1, min(24, int(grid_rows)))
    title_rows = max(1, min(4, int(title_height)))
    footer_rows = max(1, min(4, int(footer_height)))

    header_widgets = _sanitize_region_widgets(header_widgets_raw, cols, title_rows, "header")
    footer_widgets = _sanitize_region_widgets(footer_widgets_raw, cols, footer_rows, "footer")

    layout_cfg = {
        "orientation": "landscape",
        "grid": {"columns": cols, "rows": rows},
        "size": {"width": 600, "height": 448},
        "regions": {
            "title_bar": {
                "enabled": title_enabled == "on",
                "height": title_rows,
                "widgets": header_widgets,
            },
            "footer": {
                "enabled": footer_enabled == "on",
                "height": footer_rows,
                "widgets": footer_widgets,
            },
        },
    }

    refresh_defaults = dict(dashboard.refresh_defaults or {})
    refresh_defaults["layout"] = layout_cfg
    dashboard.timezone = timezone.strip() or "America/Chicago"
    dashboard.widgets = clean_widgets
    dashboard.refresh_defaults = refresh_defaults
    dashboard.updated_at = _utcnow()

    session.add(dashboard)
    session.commit()
    return RedirectResponse(url=f"/designer?dashboard_id={dashboard.id}&msg=Designer+saved", status_code=302)


@app.post("/designer/refresh-now")
def designer_refresh_now(request: Request, session: Session = Depends(get_session), dashboard_id: str = Form(...)) -> RedirectResponse:
    auth = _require_ui_auth(request)
    if auth:
        return auth

    dashboard = session.get(Dashboard, dashboard_id)
    if dashboard is None:
        return RedirectResponse(url="/designer?msg=Dashboard+not+found", status_code=302)

    refresh_dashboard_widgets(session, dashboard, force=True)
    return RedirectResponse(url=f"/designer?dashboard_id={dashboard.id}&msg=Refresh+requested", status_code=302)


@app.get("/devices", response_class=HTMLResponse)
def devices_page(request: Request, session: Session = Depends(get_session) ) -> Response:
    auth = _require_ui_auth(request)
    if auth:
        return auth

    dashboards = session.exec(select(Dashboard)).all()
    devices = session.exec(select(Device)).all()
    assignments = session.exec(select(DeviceAssignment)).all()
    firmware_images = session.exec(select(FirmwareImage).where(FirmwareImage.active == True)).all()  # noqa: E712
    assignment_by_device = {a.device_id: a for a in assignments}
    dashboard_by_id = {d.id: d for d in dashboards}

    return _render(
        request,
        "devices.html",
        {
            "active_tab": "devices",
            "devices": devices,
            "dashboards": dashboards,
            "assignment_by_device": assignment_by_device,
            "dashboard_by_id": dashboard_by_id,
            "firmware_images": firmware_images,
            "message": request.query_params.get("msg", ""),
        },
    )

@app.post("/devices/add")
def devices_add(
    request: Request,
    session: Session = Depends(get_session),
    name: str = Form(...),
    panel_profile: str = Form("solum_ed057tc6_baseline"),
    platformio_env: str = Form("seeed_xiao_esp32c6_solum_baseline_locked"),
    supports_direct_fetch: str | None = Form(default=None),
) -> RedirectResponse:
    auth = _require_ui_auth(request)
    if auth:
        return auth

    row = Device(
        name=name.strip() or "Device",
        panel_profile=panel_profile.strip() or "solum_ed057tc6_baseline",
        platformio_env=platformio_env.strip() or "seeed_xiao_esp32c6_solum_baseline_locked",
        supports_direct_fetch=supports_direct_fetch == "on",
    )
    session.add(row)
    session.commit()
    return RedirectResponse(url="/devices?msg=Device+added", status_code=302)


@app.post("/devices/delete")
def devices_delete(request: Request, session: Session = Depends(get_session), device_id: str = Form(...)) -> RedirectResponse:
    auth = _require_ui_auth(request)
    if auth:
        return auth

    row = session.get(Device, device_id)
    if row is None:
        return RedirectResponse(url="/devices?msg=Device+not+found", status_code=302)

    assignments = session.exec(select(DeviceAssignment).where(DeviceAssignment.device_id == device_id)).all()
    for assignment in assignments:
        session.delete(assignment)
    session.delete(row)
    session.commit()
    return RedirectResponse(url="/devices?msg=Device+deleted", status_code=302)


@app.post("/devices/rotate-token")
def devices_rotate_token(request: Request, session: Session = Depends(get_session), device_id: str = Form(...)) -> RedirectResponse:
    auth = _require_ui_auth(request)
    if auth:
        return auth

    row = session.get(Device, device_id)
    if row is None:
        return RedirectResponse(url="/devices?msg=Device+not+found", status_code=302)

    row.auth_token = next_widget_id("tok") + next_widget_id("tok")
    row.updated_at = _utcnow()
    session.add(row)
    session.commit()
    return RedirectResponse(url="/devices?msg=Token+rotated", status_code=302)


@app.post("/devices/assign")
def devices_assign(
    request: Request,
    session: Session = Depends(get_session),
    device_id: str = Form(...),
    dashboard_id: str = Form(""),
    enabled: str | None = Form(default=None),
    override_panel_profile: str = Form(""),
    override_platformio_env: str = Form(""),
) -> RedirectResponse:
    auth = _require_ui_auth(request)
    if auth:
        return auth

    assignment = session.exec(select(DeviceAssignment).where(DeviceAssignment.device_id == device_id)).first()

    if not dashboard_id.strip():
        if assignment is not None:
            session.delete(assignment)
            session.commit()
        return RedirectResponse(url="/devices?msg=Assignment+cleared", status_code=302)

    dashboard = session.get(Dashboard, dashboard_id)
    if dashboard is None:
        return RedirectResponse(url="/devices?msg=Dashboard+not+found", status_code=302)

    overrides: dict[str, Any] = {}
    if override_panel_profile.strip():
        overrides["panel_profile"] = override_panel_profile.strip()
    if override_platformio_env.strip():
        overrides["platformio_env"] = override_platformio_env.strip()

    if assignment is None:
        assignment = DeviceAssignment(
            dashboard_id=dashboard.id,
            device_id=device_id,
            enabled=enabled == "on",
            overrides=overrides,
        )
    else:
        assignment.dashboard_id = dashboard.id
        assignment.enabled = enabled == "on"
        assignment.overrides = overrides
        assignment.updated_at = _utcnow()

    session.add(assignment)
    session.commit()
    return RedirectResponse(url="/devices?msg=Assignment+saved", status_code=302)


@app.get("/integrations", response_class=HTMLResponse)
def integrations_page(request: Request, session: Session = Depends(get_session) ) -> Response:
    auth = _require_ui_auth(request)
    if auth:
        return auth

    presets = session.exec(select(IntegrationPreset).order_by(IntegrationPreset.category, IntegrationPreset.name)).all()
    return _render(
        request,
        "integrations.html",
        {"active_tab": "integrations", "presets": presets, "message": request.query_params.get("msg", "")},
    )


@app.post("/integrations/add")
def integrations_add(
    request: Request,
    session: Session = Depends(get_session),
    name: str = Form(...),
    slug: str = Form(...),
    category: str = Form(...),
    provider: str = Form(...),
    auth_type: str = Form("none"),
    docs_url: str = Form(""),
    description: str = Form(""),
    config_template_json: str = Form("{}"),
) -> RedirectResponse:
    auth = _require_ui_auth(request)
    if auth:
        return auth

    existing = session.exec(select(IntegrationPreset).where(IntegrationPreset.slug == slug.strip())).first()
    if existing:
        return RedirectResponse(url="/integrations?msg=Slug+already+exists", status_code=302)

    try:
        config_template = json.loads(config_template_json)
        if not isinstance(config_template, dict):
            raise ValueError("not object")
    except Exception:
        return RedirectResponse(url="/integrations?msg=Invalid+JSON+config+template", status_code=302)

    session.add(
        IntegrationPreset(
            name=name.strip(),
            slug=slug.strip(),
            category=category.strip() or "general",
            provider=provider.strip(),
            auth_type=auth_type.strip() or "none",
            docs_url=docs_url.strip(),
            description=description.strip(),
            config_template=config_template,
            is_default=False,
            enabled=True,
        )
    )
    session.commit()
    return RedirectResponse(url="/integrations?msg=Integration+preset+added", status_code=302)


@app.post("/integrations/delete")
def integrations_delete(request: Request, session: Session = Depends(get_session), preset_id: str = Form(...)) -> RedirectResponse:
    auth = _require_ui_auth(request)
    if auth:
        return auth

    row = session.get(IntegrationPreset, preset_id)
    if row is None:
        return RedirectResponse(url="/integrations?msg=Preset+not+found", status_code=302)
    if row.is_default:
        return RedirectResponse(url="/integrations?msg=Default+presets+cannot+be+deleted", status_code=302)

    session.delete(row)
    session.commit()
    return RedirectResponse(url="/integrations?msg=Preset+deleted", status_code=302)


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "service": settings.app_name,
        "time_utc": _utcnow().isoformat(),
        "env": settings.app_env,
    }


@app.get("/api/templates")
def list_templates(session: Session = Depends(get_session)) -> list[Template]:
    return session.exec(select(Template)).all()


@app.post("/api/templates")
def create_template(payload: TemplateCreate, session: Session = Depends(get_session)) -> Template:
    existing = session.exec(select(Template).where(Template.slug == payload.slug)).first()
    if existing:
        raise HTTPException(status_code=409, detail="Template slug already exists.")
    row = Template(**payload.model_dump())
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


@app.get("/api/dashboards")
def list_dashboards(session: Session = Depends(get_session)) -> list[Dashboard]:
    return session.exec(select(Dashboard)).all()


@app.post("/api/dashboards")
def create_dashboard(payload: DashboardCreate, session: Session = Depends(get_session)) -> Dashboard:
    template = session.get(Template, payload.template_id)
    if template is None:
        raise HTTPException(status_code=404, detail="Template not found.")
    row = Dashboard(**payload.model_dump())
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


@app.get("/api/dashboards/{dashboard_id}")
def get_dashboard(dashboard_id: str, session: Session = Depends(get_session)) -> Dashboard:
    row = session.get(Dashboard, dashboard_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Dashboard not found.")
    return row


@app.patch("/api/dashboards/{dashboard_id}")
def patch_dashboard(dashboard_id: str, payload: DashboardPatch, session: Session = Depends(get_session)) -> Dashboard:
    row = session.get(Dashboard, dashboard_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Dashboard not found.")
    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(row, field, value)
    row.updated_at = _utcnow()
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


@app.post("/api/dashboards/{dashboard_id}/refresh-now", response_model=ManualRefreshResponse)
def refresh_dashboard_now(dashboard_id: str, session: Session = Depends(get_session)) -> ManualRefreshResponse:
    row = session.get(Dashboard, dashboard_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Dashboard not found.")
    refreshed, skipped = refresh_dashboard_widgets(session, row, force=True)
    return ManualRefreshResponse(dashboard_id=dashboard_id, refreshed_widgets=refreshed, skipped_widgets=skipped)


@app.get("/api/devices")
def list_devices(session: Session = Depends(get_session)) -> list[Device]:
    return session.exec(select(Device)).all()


@app.post("/api/devices")
def create_device(payload: DeviceCreate, session: Session = Depends(get_session)) -> Device:
    row = Device(**payload.model_dump())
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


@app.get("/api/assignments")
def list_assignments(session: Session = Depends(get_session)) -> list[DeviceAssignment]:
    return session.exec(select(DeviceAssignment)).all()


@app.post("/api/assignments")
def create_assignment(payload: AssignmentCreate, session: Session = Depends(get_session)) -> DeviceAssignment:
    dashboard = session.get(Dashboard, payload.dashboard_id)
    device = session.get(Device, payload.device_id)
    if dashboard is None:
        raise HTTPException(status_code=404, detail="Dashboard not found.")
    if device is None:
        raise HTTPException(status_code=404, detail="Device not found.")
    existing = session.exec(
        select(DeviceAssignment).where(
            DeviceAssignment.dashboard_id == payload.dashboard_id,
            DeviceAssignment.device_id == payload.device_id,
        )
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Assignment already exists.")
    row = DeviceAssignment(**payload.model_dump())
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def _validate_device_token(device: Device, token: str | None) -> None:
    if not token or token != device.auth_token:
        raise HTTPException(status_code=401, detail="Invalid device token.")


@app.post("/api/devices/{device_id}/heartbeat")
def device_heartbeat(
    device_id: str,
    payload: DeviceHeartbeat,
    session: Session = Depends(get_session),
    x_device_token: str | None = Header(default=None, alias="X-Device-Token"),
) -> dict[str, Any]:
    row = session.get(Device, device_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Device not found.")
    _validate_device_token(row, x_device_token)
    if payload.firmware_version is not None:
        row.firmware_version = payload.firmware_version
    if payload.panel_profile is not None:
        row.panel_profile = payload.panel_profile
    row.status = payload.status
    row.last_seen_at = _utcnow()
    row.updated_at = _utcnow()
    metadata = dict(row.metadata_json or {})
    if payload.ip_address is not None:
        metadata["ip_address"] = payload.ip_address
    if payload.wifi_rssi is not None:
        metadata["wifi_rssi"] = payload.wifi_rssi
    if payload.extra:
        metadata.update(payload.extra)
    row.metadata_json = metadata
    session.add(row)
    session.commit()
    return {"status": "ok", "device_id": row.id, "last_seen_at": row.last_seen_at.isoformat()}


@app.get("/api/devices/{device_id}/manifest", response_model=DeviceManifestResponse)
def get_device_manifest(
    device_id: str,
    session: Session = Depends(get_session),
    token: str | None = Query(default=None),
    x_device_token: str | None = Header(default=None, alias="X-Device-Token"),
) -> DeviceManifestResponse:
    row = session.get(Device, device_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Device not found.")

    _validate_device_token(row, x_device_token or token)
    assignment = session.exec(
        select(DeviceAssignment).where(
            DeviceAssignment.device_id == row.id,
            DeviceAssignment.enabled == True,  # noqa: E712
        )
    ).first()
    if assignment is None:
        raise HTTPException(status_code=404, detail="No enabled assignment for this device.")

    dashboard = session.get(Dashboard, assignment.dashboard_id)
    if dashboard is None or not dashboard.enabled:
        raise HTTPException(status_code=404, detail="Assigned dashboard not found or disabled.")

    return DeviceManifestResponse(**build_manifest(session, row, assignment, dashboard))







@app.get("/designer/preview-data")
def designer_preview_data(
    request: Request,
    dashboard_id: str,
    force: int = 0,
    session: Session = Depends(get_session),
) -> Response:
    auth = _require_ui_auth(request)
    if auth:
        return auth

    dashboard = session.get(Dashboard, dashboard_id)
    if dashboard is None:
        return JSONResponse({"error": "dashboard_not_found"}, status_code=404)

    if force:
        refresh_dashboard_widgets(session, dashboard, force=True)

    snapshot_rows = session.exec(select(DataSnapshot).where(DataSnapshot.dashboard_id == dashboard_id)).all()
    snapshot_map = {row.widget_id: row for row in snapshot_rows}

    widgets_out: list[dict[str, Any]] = []
    for widget in dashboard.widgets:
        wid = str(widget.get("id", "")).strip()
        if not wid:
            continue
        snap = snapshot_map.get(wid)
        widgets_out.append(
            {
                "id": wid,
                "type": widget.get("type", ""),
                "title": widget.get("title", ""),
                "layout": widget.get("layout", {}),
                "data": snap.payload if snap else {},
                "cache": {
                    "fetched_at": snap.fetched_at.isoformat() if snap else None,
                    "expires_at": snap.expires_at.isoformat() if (snap and snap.expires_at) else None,
                    "error": snap.error if snap else "",
                },
            }
        )

    return JSONResponse(
        {
            "dashboard_id": dashboard.id,
            "generated_at": _utcnow().isoformat(),
            "widgets": widgets_out,
        }
    )


@app.post("/devices/provision-raw")
def devices_provision_raw(
    request: Request,
    session: Session = Depends(get_session),
    name: str = Form(""),
    dashboard_id: str = Form(""),
    panel_profile: str = Form("solum_ed057tc6_baseline"),
    platformio_env: str = Form("seeed_xiao_esp32c6_solum_baseline_locked"),
) -> RedirectResponse:
    auth = _require_ui_auth(request)
    if auth:
        return auth

    claim_code = next_widget_id("CLAIM").replace("_", "").upper()[:10]
    expires_at = (_utcnow() + timedelta(hours=24)).replace(microsecond=0)

    device = Device(
        name=name.strip() or f"raw-{claim_code.lower()}",
        panel_profile=panel_profile.strip() or "solum_ed057tc6_baseline",
        platformio_env=platformio_env.strip() or "seeed_xiao_esp32c6_solum_baseline_locked",
        status="provisioning",
        metadata_json={
            "claim_code": claim_code,
            "claim_status": "pending",
            "claim_created_at": _utcnow().isoformat(),
            "claim_expires_at": expires_at.isoformat(),
        },
    )
    session.add(device)
    session.commit()
    session.refresh(device)

    if dashboard_id.strip():
        dashboard = session.get(Dashboard, dashboard_id.strip())
        if dashboard is not None:
            assignment = DeviceAssignment(
                dashboard_id=dashboard.id,
                device_id=device.id,
                enabled=True,
                overrides={},
            )
            session.add(assignment)
            session.commit()

    msg = f"Raw device created. Claim code: {claim_code}"
    return RedirectResponse(url=f"/devices?msg={msg.replace(' ', '+')}", status_code=302)


@app.get("/api/firmware-images")
def list_firmware_images(request: Request, session: Session = Depends(get_session)) -> Response:
    auth = _require_ui_auth(request)
    if auth:
        return auth

    images = session.exec(select(FirmwareImage).order_by(FirmwareImage.created_at.desc())).all()
    return JSONResponse(
        [
            {
                "id": row.id,
                "name": row.name,
                "slug": row.slug,
                "board": row.board,
                "panel_profile": row.panel_profile,
                "platformio_env": row.platformio_env,
                "version": row.version,
                "binary_url": row.binary_url,
                "notes": row.notes,
                "active": row.active,
                "is_default": row.is_default,
            }
            for row in images
        ]
    )


@app.post("/firmware/add")
def add_firmware_image(
    request: Request,
    session: Session = Depends(get_session),
    name: str = Form(...),
    slug: str = Form(...),
    board: str = Form("seeed_xiao_esp32c6"),
    panel_profile: str = Form("solum_ed057tc6_baseline"),
    platformio_env: str = Form("seeed_xiao_esp32c6_solum_baseline_locked"),
    version: str = Form("0.1.0"),
    binary_url: str = Form(""),
    notes: str = Form(""),
) -> RedirectResponse:
    auth = _require_ui_auth(request)
    if auth:
        return auth

    exists = session.exec(select(FirmwareImage).where(FirmwareImage.slug == slug.strip())).first()
    if exists:
        return RedirectResponse(url="/devices?msg=Firmware+slug+already+exists", status_code=302)

    session.add(
        FirmwareImage(
            name=name.strip(),
            slug=slug.strip(),
            board=board.strip() or "seeed_xiao_esp32c6",
            panel_profile=panel_profile.strip() or "solum_ed057tc6_baseline",
            platformio_env=platformio_env.strip() or "seeed_xiao_esp32c6_solum_baseline_locked",
            version=version.strip() or "0.1.0",
            binary_url=binary_url.strip(),
            notes=notes.strip(),
            is_default=False,
            active=True,
        )
    )
    session.commit()
    return RedirectResponse(url="/devices?msg=Firmware+image+added", status_code=302)


@app.post("/firmware/delete")
def delete_firmware_image(request: Request, session: Session = Depends(get_session), firmware_id: str = Form(...)) -> RedirectResponse:
    auth = _require_ui_auth(request)
    if auth:
        return auth

    row = session.get(FirmwareImage, firmware_id)
    if row is None:
        return RedirectResponse(url="/devices?msg=Firmware+image+not+found", status_code=302)
    if row.is_default:
        return RedirectResponse(url="/devices?msg=Default+firmware+image+cannot+be+deleted", status_code=302)

    session.delete(row)
    session.commit()
    return RedirectResponse(url="/devices?msg=Firmware+image+deleted", status_code=302)


@app.post("/api/provision/claim")
def provision_claim(payload: ProvisionClaimRequest, session: Session = Depends(get_session)) -> JSONResponse:
    claim_code = payload.claim_code.strip().upper()
    if not claim_code:
        return JSONResponse({"error": "missing_claim_code"}, status_code=400)

    devices = session.exec(select(Device)).all()
    for device in devices:
        meta = device.metadata_json if isinstance(device.metadata_json, dict) else {}
        if str(meta.get("claim_code", "")).upper() != claim_code:
            continue
        if str(meta.get("claim_status", "")).lower() != "pending":
            return JSONResponse({"error": "claim_not_pending"}, status_code=409)

        expiry_raw = str(meta.get("claim_expires_at", "")).strip()
        if expiry_raw:
            try:
                expiry_dt = datetime.fromisoformat(expiry_raw)
                if expiry_dt.tzinfo is None:
                    expiry_dt = expiry_dt.replace(tzinfo=timezone.utc)
                if expiry_dt < _utcnow().astimezone(expiry_dt.tzinfo):
                    return JSONResponse({"error": "claim_expired"}, status_code=410)
            except ValueError:
                pass

        device.status = "online"
        if payload.firmware_version.strip():
            device.firmware_version = payload.firmware_version.strip()
        if payload.panel_profile.strip():
            device.panel_profile = payload.panel_profile.strip()
        if payload.platformio_env.strip():
            device.platformio_env = payload.platformio_env.strip()

        meta["claim_status"] = "claimed"
        meta["claimed_at"] = _utcnow().isoformat()
        if payload.device_uid.strip():
            meta["device_uid"] = payload.device_uid.strip()
        device.metadata_json = meta
        device.updated_at = _utcnow()

        session.add(device)
        session.commit()
        session.refresh(device)

        return JSONResponse(
            {
                "status": "claimed",
                "device_id": device.id,
                "auth_token": device.auth_token,
                "panel_profile": device.panel_profile,
                "platformio_env": device.platformio_env,
                "manifest_url": f"/api/devices/{device.id}/manifest",
                "heartbeat_url": f"/api/devices/{device.id}/heartbeat",
            }
        )

    return JSONResponse({"error": "claim_not_found"}, status_code=404)





@app.get("/firmware/web-manifest/{firmware_id}")
def firmware_web_manifest(request: Request, firmware_id: str, session: Session = Depends(get_session)) -> Response:
    auth = _require_ui_auth(request)
    if auth:
        return auth

    row = session.get(FirmwareImage, firmware_id)
    if row is None:
        return JSONResponse({"error": "firmware_not_found"}, status_code=404)
    if not row.binary_url:
        return JSONResponse({"error": "binary_url_missing"}, status_code=400)

    return JSONResponse(
        {
            "name": row.name,
            "version": row.version,
            "new_install_prompt_erase": True,
            "builds": [
                {
                    "chipFamily": "ESP32-C6",
                    "parts": [
                        {
                            "path": row.binary_url,
                            "offset": 0,
                        }
                    ],
                }
            ],
        }
    )








