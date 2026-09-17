"""配置管理模块"""

import json
import os
from pathlib import Path
from typing import Any, Literal

from dotenv import load_dotenv
from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings

# 加载环境变量
# 首先尝试加载当前目录的.env
load_dotenv()

# 然后尝试加载HelloAgents的.env(如果存在)
helloagents_env = Path(__file__).parent.parent.parent.parent / "HelloAgents" / ".env"
if helloagents_env.exists():
    load_dotenv(helloagents_env, override=False)  # 不覆盖已有的环境变量


class Settings(BaseSettings):
    """应用配置"""

    # 应用基本配置
    app_name: str = "HelloAgents智能旅行助手"
    app_version: str = "2.0.0"
    debug: bool = False

    # 服务器配置
    host: str = "0.0.0.0"
    port: int = 8000

    # CORS配置 - 使用字符串,在代码中分割
    cors_origins: str = (
        "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173,http://127.0.0.1:3000"
    )

    # 高德地图API配置
    vite_amap_web_key: str = ""
    vite_amap_web_js_key: str = ""
    vite_amap_security_js_code: str = ""

    # Optional Ctrip Wendao attraction supplement. Disabled unless both flag and key are set.
    tripai_enabled: bool = False
    tripai_api_key: SecretStr = SecretStr("")
    tripai_base_url: str = "https://wendao-skill-prod.ctrip.com/skill/query"
    tripai_timeout: float = Field(default=30, ge=1, le=60)

    # Google Maps API配置
    google_maps_api_key: str = ""
    google_maps_proxy: str = ""

    # Deprecated compatibility fields. No runtime path reads or enables them.
    xhs_cookie: str = ""
    xhs_enabled: bool = False

    # 联网研究配置（Key 仅供后端使用，不进入运行时设置 API）
    brave_search_api_key: str = ""
    brave_search_base_url: str = "https://api.search.brave.com/res/v1/web/search"
    web_research_timeout: float = Field(default=10, ge=1, le=60)
    web_research_result_count: int = Field(default=5, ge=1, le=20)
    web_research_official_domains: str = ""
    source_cache_ttl_seconds: int = Field(default=21600, ge=60, le=604800)

    # LLM配置 (从环境变量读取,由HelloAgents管理)
    openai_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("OPENAI_API_KEY", "LLM_API_KEY"),
    )
    openai_base_url: str = Field(
        default="https://api.openai.com/v1",
        validation_alias=AliasChoices("OPENAI_BASE_URL", "LLM_BASE_URL"),
    )
    openai_model: str = Field(
        default="gpt-4",
        validation_alias=AliasChoices("OPENAI_MODEL", "LLM_MODEL_ID"),
    )
    legacy_json_repair: bool = True
    planner_engine: Literal["legacy", "journey_graph"] = "legacy"
    planner_compare_engines: bool = False
    demo_mode: bool = False
    weather_enabled: bool = False
    weather_mcp_python: str = "/opt/weather/bin/python"
    travel_train_enabled: bool = False
    one_click_travel_enabled: bool = False
    travel_hotel_enabled: bool = False
    travel_flight_enabled: bool = False
    travel_mcp_python: str = "/opt/weather/bin/python"
    travel_mcp_node: str = "node"
    travel_mcp_modules: str = "/opt/travel-mcp/node_modules"
    rollinggo_api_key: SecretStr = SecretStr("")
    variflight_api_key: SecretStr = SecretStr("")
    # Non-expiring, atomic Redis counter per credential; operator raises the cumulative ceiling.
    travel_flight_call_limit: int = Field(default=0, ge=0, le=100000)
    demo_node_delay_seconds: float = Field(default=0, ge=0, le=2)
    runtime_secret_updates_enabled: bool = False
    api_docs_enabled: bool = True

    # Phase 7 observability and budget accounting. Prices are operator-supplied.
    llm_input_cost_per_million_usd: float = Field(default=0, ge=0)
    llm_output_cost_per_million_usd: float = Field(default=0, ge=0)
    llm_structured_max_tokens: int = Field(default=32768, ge=512, le=384000)
    llm_structured_max_attempts: int = Field(default=2, ge=1, le=3)
    llm_max_tokens_per_trip: int = Field(default=80000, ge=1024, le=1000000)
    llm_max_cost_per_trip_usd: float = Field(default=2.0, gt=0, le=1000)

    # Cost-bearing API protection. Access codes are never exposed by runtime settings.
    api_access_code_required: bool = False
    api_access_code: SecretStr = SecretStr("")
    api_rate_limit_enabled: bool = False
    api_rate_limit_requests: int = Field(default=6, ge=1, le=10000)
    api_rate_limit_window_seconds: int = Field(default=60, ge=1, le=86400)
    api_max_active_trip_tasks: int = Field(default=4, ge=1, le=1000)
    api_max_request_bytes: int = Field(default=32768, ge=1024, le=1048576)

    # 日志配置
    log_level: str = "INFO"

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"  # 忽略额外的环境变量

    def get_cors_origins_list(self) -> list[str]:
        """获取CORS origins列表"""
        return [origin.strip() for origin in self.cors_origins.split(",")]


# 创建全局配置实例
settings = Settings()
_RUNTIME_SETTINGS_FILE = Path(__file__).resolve().parent.parent / "runtime_settings.json"
_RUNTIME_SETTING_KEYS = {
    "vite_amap_web_key",
    "vite_amap_web_js_key",
    "google_maps_api_key",
    "google_maps_proxy",
    "openai_api_key",
    "openai_base_url",
    "openai_model",
}


def _load_runtime_overrides() -> dict[str, Any]:
    """加载本地持久化的运行时配置覆盖项。"""
    if not _RUNTIME_SETTINGS_FILE.exists():
        return {}
    try:
        with open(_RUNTIME_SETTINGS_FILE, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return {k: data[k] for k in _RUNTIME_SETTING_KEYS if k in data}
    except Exception as e:
        print(f"⚠️  读取运行时配置失败，已回退到环境变量: {e}")
    return {}


def _persist_runtime_overrides(overrides: dict[str, Any]) -> None:
    """持久化运行时配置覆盖项。"""
    _RUNTIME_SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(_RUNTIME_SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(overrides, f, ensure_ascii=False, indent=2)


def _sync_env_from_settings() -> None:
    """将运行时配置同步到环境变量，兼容读取 env 的第三方组件。"""
    if settings.openai_api_key:
        os.environ["OPENAI_API_KEY"] = settings.openai_api_key
        os.environ["LLM_API_KEY"] = settings.openai_api_key
    if settings.openai_base_url:
        os.environ["OPENAI_BASE_URL"] = settings.openai_base_url
        os.environ["LLM_BASE_URL"] = settings.openai_base_url
    if settings.openai_model:
        os.environ["OPENAI_MODEL"] = settings.openai_model
        os.environ["LLM_MODEL_ID"] = settings.openai_model


def _apply_runtime_overrides(overrides: dict[str, Any]) -> None:
    """将覆盖项应用到全局 settings 实例。"""
    for key, value in overrides.items():
        if key in _RUNTIME_SETTING_KEYS and hasattr(settings, key):
            setattr(settings, key, value if value is not None else "")
    _sync_env_from_settings()


_runtime_overrides = _load_runtime_overrides()
_apply_runtime_overrides(_runtime_overrides)


def get_settings() -> Settings:
    """获取配置实例"""
    return settings


def get_runtime_settings() -> dict[str, str | bool]:
    """Return browser-safe runtime status without disclosing backend secrets."""
    return {
        "vite_amap_web_js_key": settings.vite_amap_web_js_key or "",
        "vite_amap_security_js_code": settings.vite_amap_security_js_code or "",
        "openai_base_url": settings.openai_base_url or "",
        "openai_model": settings.openai_model or "",
        "demo_mode": settings.demo_mode,
        "planner_engine": settings.planner_engine,
        "llm_configured": bool(settings.openai_api_key),
        "amap_web_configured": bool(settings.vite_amap_web_key),
        "amap_web_js_configured": bool(settings.vite_amap_web_js_key),
        "google_maps_configured": bool(settings.google_maps_api_key),
        "runtime_secret_updates_enabled": settings.runtime_secret_updates_enabled,
    }


def update_runtime_settings(updates: dict[str, Any]) -> dict[str, str | bool]:
    """更新并持久化运行时配置。"""
    global _runtime_overrides

    normalized: dict[str, str] = {}
    for key, value in updates.items():
        if key not in _RUNTIME_SETTING_KEYS:
            continue
        normalized[key] = str(value).strip() if value is not None else ""

    _runtime_overrides.update(normalized)
    _persist_runtime_overrides(_runtime_overrides)
    _apply_runtime_overrides(_runtime_overrides)
    return get_runtime_settings()


# 验证必要的配置
def validate_config():
    """验证配置是否完整"""
    warnings = []
    if settings.api_access_code_required and not settings.api_access_code.get_secret_value():
        raise ValueError("API_ACCESS_CODE is required when API_ACCESS_CODE_REQUIRED=true")

    if not settings.vite_amap_web_key:
        warnings.append("VITE_AMAP_WEB_KEY未配置，景点地理编码等功能将不可用")

    llm_api_key = settings.openai_api_key or os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not llm_api_key and not settings.demo_mode:
        warnings.append("LLM API Key未配置，AI 生成功能将不可用")

    if warnings:
        print("\n⚠️  配置警告:")
        for w in warnings:
            print(f"  - {w}")

    return True


# 打印配置信息(用于调试)
def print_config():
    """打印当前配置(隐藏敏感信息)"""
    print(f"应用名称: {settings.app_name}")
    print(f"版本: {settings.app_version}")
    print(f"服务器: {settings.host}:{settings.port}")
    print(f"高德地图API Key: {'已配置' if settings.vite_amap_web_key else '未配置'}")
    print(f"高德地图JS Key: {'已配置' if settings.vite_amap_web_js_key else '未配置'}")
    print(f"Google Maps API Key: {'已配置' if settings.google_maps_api_key else '未配置'}")
    print(f"Google Maps Proxy: {settings.google_maps_proxy or '未配置'}")
    print(f"Demo 模式: {'已启用' if settings.demo_mode else '未启用'}")

    # 检查LLM配置
    llm_api_key = settings.openai_api_key or os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
    llm_base_url = settings.openai_base_url
    llm_model = settings.openai_model

    print(f"LLM API Key: {'已配置' if llm_api_key else '未配置'}")
    print(f"LLM Base URL: {llm_base_url}")
    print(f"LLM Model: {llm_model}")
    print(f"日志级别: {settings.log_level}")
