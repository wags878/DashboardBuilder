import secrets
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel

from app.db import utcnow


def new_id() -> str:
    return str(uuid.uuid4())


def new_token() -> str:
    return secrets.token_urlsafe(24)


class Template(SQLModel, table=True):
    id: str = Field(default_factory=new_id, primary_key=True)
    name: str = Field(index=True, max_length=120)
    slug: str = Field(index=True, unique=True, max_length=120)
    description: str = ""
    version: str = "1.0.0"
    layout: dict[str, Any] = Field(default_factory=dict, sa_column=Column("layout", JSON))
    default_widgets: list[dict[str, Any]] = Field(
        default_factory=list,
        sa_column=Column("default_widgets", JSON),
    )
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class Dashboard(SQLModel, table=True):
    id: str = Field(default_factory=new_id, primary_key=True)
    name: str = Field(index=True, max_length=120)
    template_id: str = Field(index=True)
    timezone: str = "America/Chicago"
    widgets: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column("widgets", JSON))
    refresh_defaults: dict[str, Any] = Field(
        default_factory=lambda: {"minimum_minutes": 5},
        sa_column=Column("refresh_defaults", JSON),
    )
    enabled: bool = True
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class Device(SQLModel, table=True):
    id: str = Field(default_factory=new_id, primary_key=True)
    name: str = Field(index=True, max_length=120)
    panel_profile: str = Field(default="solum_ed057tc6_baseline", max_length=120)
    platformio_env: str = Field(default="seeed_xiao_esp32c6_solum_baseline_locked", max_length=160)
    firmware_version: str = ""
    auth_token: str = Field(default_factory=new_token, index=True, unique=True, max_length=128)
    supports_direct_fetch: bool = True
    status: str = Field(default="offline", max_length=40)
    last_seen_at: datetime | None = None
    metadata_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column("metadata_json", JSON))
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class DeviceAssignment(SQLModel, table=True):
    id: str = Field(default_factory=new_id, primary_key=True)
    dashboard_id: str = Field(index=True)
    device_id: str = Field(index=True)
    enabled: bool = True
    overrides: dict[str, Any] = Field(default_factory=dict, sa_column=Column("overrides", JSON))
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class DataSnapshot(SQLModel, table=True):
    id: str = Field(default_factory=new_id, primary_key=True)
    dashboard_id: str = Field(index=True)
    widget_id: str = Field(index=True)
    payload: dict[str, Any] = Field(default_factory=dict, sa_column=Column("payload", JSON))
    fetched_at: datetime = Field(default_factory=utcnow)
    expires_at: datetime | None = None
    error: str = ""


class IntegrationPreset(SQLModel, table=True):
    id: str = Field(default_factory=new_id, primary_key=True)
    name: str = Field(index=True, max_length=120)
    slug: str = Field(index=True, unique=True, max_length=140)
    category: str = Field(default="general", max_length=60)
    provider: str = Field(default="", max_length=80)
    description: str = ""
    auth_type: str = Field(default="none", max_length=60)
    docs_url: str = ""
    config_template: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column("config_template", JSON),
    )
    is_default: bool = True
    enabled: bool = True
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)