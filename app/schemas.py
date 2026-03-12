from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class TemplateCreate(BaseModel):
    name: str
    slug: str
    description: str = ""
    version: str = "1.0.0"
    layout: dict[str, Any] = Field(default_factory=dict)
    default_widgets: list[dict[str, Any]] = Field(default_factory=list)


class DashboardCreate(BaseModel):
    name: str
    template_id: str
    timezone: str = "America/Chicago"
    widgets: list[dict[str, Any]] = Field(default_factory=list)
    refresh_defaults: dict[str, Any] = Field(default_factory=lambda: {"minimum_minutes": 5})
    enabled: bool = True


class DashboardPatch(BaseModel):
    name: str | None = None
    timezone: str | None = None
    widgets: list[dict[str, Any]] | None = None
    refresh_defaults: dict[str, Any] | None = None
    enabled: bool | None = None


class DeviceCreate(BaseModel):
    name: str
    panel_profile: str = "solum_ed057tc6_baseline"
    platformio_env: str = "seeed_xiao_esp32c6_solum_baseline_locked"
    firmware_version: str = ""
    supports_direct_fetch: bool = True
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class AssignmentCreate(BaseModel):
    dashboard_id: str
    device_id: str
    enabled: bool = True
    overrides: dict[str, Any] = Field(default_factory=dict)


class DeviceHeartbeat(BaseModel):
    firmware_version: str | None = None
    ip_address: str | None = None
    wifi_rssi: int | None = None
    panel_profile: str | None = None
    status: str = "online"
    extra: dict[str, Any] = Field(default_factory=dict)


class DeviceManifestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    generated_at: datetime
    device_id: str
    panel_profile: str
    platformio_env: str
    dashboard: dict[str, Any]
    widgets: list[dict[str, Any]]


class ManualRefreshResponse(BaseModel):
    dashboard_id: str
    refreshed_widgets: list[str]
    skipped_widgets: list[str]
class ProvisionClaimRequest(BaseModel):
    claim_code: str
    device_uid: str = ""
    firmware_version: str = ""
    panel_profile: str = ""
    platformio_env: str = ""
