"""YAML configuration loading, environment overrides, and schema validation.

Load order (later wins):

1. ``config/default.yaml`` - built-in defaults
2. ``config/env/<APP_ENV>.yaml`` - per-environment override
3. Environment variables: ``APP_ENV``, ``LOG_LEVEL``, ``MONGODB_URI``,
   ``MONGODB_DATABASE``, ``MONGODB_*`` timeout/pool tuning, ``API_HOST``,
   ``API_PORT``

The merged document is validated against pydantic models below, so typos and
invalid values fail fast with a :class:`ConfigurationError`.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

from aiagent.core.errors import ConfigurationError

PROJECT_ROOT = Path(__file__).resolve().parents[3]

_VALID_LOG_LEVELS = frozenset({"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})


class AppSettings(BaseModel):
    """Top-level application settings."""

    model_config = ConfigDict(extra="forbid")

    name: str = "aiagent"
    env: Literal["dev", "staging", "prod"] = "dev"
    debug: bool = False
    log_level: str = "INFO"

    @field_validator("log_level")
    @classmethod
    def _check_log_level(cls, value: str) -> str:
        level = value.upper()
        if level not in _VALID_LOG_LEVELS:
            raise ValueError(f"invalid log level: {value!r}")
        return level


class APISettings(BaseModel):
    """HTTP API binding and routing settings."""

    model_config = ConfigDict(extra="forbid")

    prefix: str = "/v1"
    host: str = "127.0.0.1"
    port: int = Field(default=8000, ge=1, le=65535)
    root_path: str = ""


class DBSettings(BaseModel):
    """MongoDB connection settings (Motor async driver)."""

    model_config = ConfigDict(extra="forbid")

    uri: str = "mongodb://localhost:27017/aiagent"
    name: str = "aiagent"
    server_selection_timeout_ms: int = Field(default=3000, ge=500)
    connect_timeout_ms: int = Field(default=5000, ge=500)
    max_pool_size: int = Field(default=10, ge=1)
    min_pool_size: int = Field(default=0, ge=0)


class HealthSettings(BaseModel):
    """Readiness probe tuning."""

    model_config = ConfigDict(extra="forbid")

    db_timeout_seconds: float = Field(default=2.0, ge=0)


class StorageSettings(BaseModel):
    """Local object storage for MVP artifacts (docs/plan/31)."""

    model_config = ConfigDict(extra="forbid")

    artifacts_dir: str = "data/artifacts"


class Settings(BaseModel):
    """Validated, merged application configuration."""

    model_config = ConfigDict(extra="forbid")

    app: AppSettings = Field(default_factory=AppSettings)
    api: APISettings = Field(default_factory=APISettings)
    db: DBSettings = Field(default_factory=DBSettings)
    health: HealthSettings = Field(default_factory=HealthSettings)
    storage: StorageSettings = Field(default_factory=StorageSettings)

    @classmethod
    def load(
        cls,
        *,
        env_override: str | None = None,
        config_dir: str | Path | None = None,
    ) -> Settings:
        """Build settings from the YAML merge chain plus environment variables."""
        cfg_dir = Path(config_dir) if config_dir else default_config_dir()
        base = _load_yaml_file(cfg_dir / "default.yaml", required=True)

        app_defaults = base.get("app", {})
        env_name = env_override or os.environ.get("APP_ENV") or app_defaults.get("env", "dev")

        env_yaml = cfg_dir / "env" / f"{env_name}.yaml"
        overrides = _load_yaml_file(env_yaml, required=False)

        merged = _deep_merge(base, overrides)
        _apply_env_overrides(merged)

        try:
            return cls.model_validate(merged)
        except Exception as exc:  # pydantic.ValidationError and friends
            raise ConfigurationError(f"invalid configuration: {exc}") from exc


def default_config_dir() -> Path:
    """Resolve the configuration directory.

    Uses ``AIAGENT_CONFIG_DIR`` when set, otherwise the repository ``config/``
    directory. Set ``AIAGENT_CONFIG_DIR`` when running from an installed package.
    """
    override = os.environ.get("AIAGENT_CONFIG_DIR")
    if override:
        return Path(override)
    return PROJECT_ROOT / "config"


def _load_yaml_file(path: Path, *, required: bool) -> dict[str, Any]:
    if not path.exists():
        if required:
            raise ConfigurationError(f"missing required config file: {path}")
        return {}
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
    except yaml.YAMLError as exc:
        raise ConfigurationError(f"invalid YAML in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigurationError(f"config file must contain a mapping: {path}")
    return data


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge ``override`` into ``base`` (dicts merge, scalars override)."""
    result = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _apply_env_overrides(merged: dict[str, Any]) -> None:
    app = merged.setdefault("app", {})
    env = os.environ.get("APP_ENV")
    if env:
        app["env"] = env
    level = os.environ.get("LOG_LEVEL")
    if level:
        app["log_level"] = level

    db = merged.setdefault("db", {})
    uri = os.environ.get("MONGODB_URI")
    if uri:
        db["uri"] = uri
    name = os.environ.get("MONGODB_DATABASE")
    if name:
        db["name"] = name
    for key in (
        "server_selection_timeout_ms",
        "connect_timeout_ms",
        "max_pool_size",
        "min_pool_size",
    ):
        env_val = os.environ.get(f"MONGODB_{key.upper()}")
        if env_val:
            db[key] = int(env_val)

    api = merged.setdefault("api", {})
    if os.environ.get("API_HOST"):
        api["host"] = os.environ["API_HOST"]
    if os.environ.get("API_PORT"):
        api["port"] = int(os.environ["API_PORT"])


@lru_cache(maxsize=1)
def load_settings() -> Settings:
    """Cached settings loader; see :meth:`Settings.load`."""
    return Settings.load()


def get_settings() -> Settings:
    """Return the process-wide settings (FastAPI dependency friendly)."""
    return load_settings()


def SETTINGS_CACHE_CLEAR() -> None:
    """Drop the cached settings (used by tests and hot reload)."""
    load_settings.cache_clear()
