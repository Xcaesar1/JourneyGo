"""Browser-safe runtime configuration status and guarded local updates."""

import secrets

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from ...config import (
    get_runtime_settings,
    update_runtime_settings,
)
from ...config import (
    get_settings as get_app_settings,
)
from ...services.amap_service import reset_amap_service
from ...services.google_map_service import reset_google_map_service
from ...services.llm_service import reset_llm

router = APIRouter(prefix="/settings", tags=["运行时配置"])


class RuntimeSettingsPayload(BaseModel):
    """前端设置页提交的运行时配置。"""

    vite_amap_web_key: str | None = Field(default=None, description="高德 Web 服务 Key")
    vite_amap_web_js_key: str | None = Field(default=None, description="高德 JS SDK Key")
    google_maps_api_key: str | None = Field(default=None, description="Google Maps API Key")
    openai_api_key: str | None = Field(default=None, description="LLM API Key")
    openai_base_url: str | None = Field(default=None, description="LLM Base URL")
    openai_model: str | None = Field(default=None, description="LLM 模型")


@router.get("")
async def get_settings():
    """Return public configuration status; secret values are never serialized."""
    return {
        "success": True,
        "message": "ok",
        "data": get_runtime_settings(),
    }


@router.put("")
async def save_settings(
    payload: RuntimeSettingsPayload,
    access_code: str | None = Header(default=None, alias="X-Access-Code"),
):
    """Allow local admin updates only behind an explicit feature flag and access code."""
    settings = get_app_settings()
    configured_code = settings.api_access_code.get_secret_value()
    if not settings.runtime_secret_updates_enabled:
        raise HTTPException(status_code=403, detail="Runtime secret updates are disabled.")
    if (
        not configured_code
        or not access_code
        or not secrets.compare_digest(access_code, configured_code)
    ):
        raise HTTPException(status_code=401, detail="A valid access code is required.")
    try:
        updates = payload.model_dump(exclude_unset=True)
        updated = update_runtime_settings(updates)

        # 重置单例，确保新配置立即生效
        reset_llm()
        reset_amap_service()
        reset_google_map_service()
        from ...agents.trip_planner_agent import reset_trip_planner_agent

        reset_trip_planner_agent()

        return {
            "success": True,
            "message": "配置已保存并立即生效",
            "data": updated,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Runtime settings update failed.") from exc
