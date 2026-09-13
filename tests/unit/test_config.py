"""Unit tests for the YAML configuration loader and validator."""

from __future__ import annotations

import pytest

from aiagent.core.config import Settings, default_config_dir
from aiagent.core.errors import ConfigurationError


def test_repo_config_dir_exists() -> None:
    assert default_config_dir().is_dir()
    assert (default_config_dir() / "default.yaml").is_file()


def test_default_values_from_repo_config() -> None:
    settings = Settings.load(env_override="dev")
    assert settings.app.name == "aiagent"
    assert settings.app.env == "dev"
    assert settings.api.host == "127.0.0.1"
    assert settings.api.port == 8000
    assert settings.db.uri.startswith("mongodb://")
    assert settings.db.name == "aiagent"
    assert settings.health.db_timeout_seconds >= 0


def test_environment_override_chain(tmp_path) -> None:
    (tmp_path / "default.yaml").write_text(
        "app:\n  env: dev\n  log_level: INFO\napi:\n  port: 8000\n"
    )
    env_dir = tmp_path / "env"
    env_dir.mkdir()
    (env_dir / "prod.yaml").write_text("app:\n  log_level: WARNING\n")

    settings = Settings.load(env_override="prod", config_dir=tmp_path)
    assert settings.app.log_level == "WARNING"
    assert settings.api.port == 8000  # scalar from default preserved


def test_environment_variable_overrides(monkeypatch, tmp_path) -> None:
    (tmp_path / "default.yaml").write_text("app:\n  env: dev\n")
    monkeypatch.setenv("MONGODB_URI", "mongodb://override:secret@db:27017/custom?authSource=custom")
    monkeypatch.setenv("MONGODB_DATABASE", "custom_db")
    monkeypatch.setenv("APP_ENV", "staging")

    settings = Settings.load(config_dir=tmp_path)
    assert settings.db.uri.startswith("mongodb://override")
    assert settings.db.name == "custom_db"
    assert settings.app.env == "staging"


def test_missing_default_config_raises(tmp_path) -> None:
    with pytest.raises(ConfigurationError, match="default.yaml"):
        Settings.load(config_dir=tmp_path)


def test_invalid_yaml_raises(tmp_path) -> None:
    (tmp_path / "default.yaml").write_text("unbalanced: [1, 2\n")
    with pytest.raises(ConfigurationError, match="invalid YAML"):
        Settings.load(config_dir=tmp_path)


def test_invalid_log_level_raises(tmp_path) -> None:
    (tmp_path / "default.yaml").write_text("app:\n  log_level: NOT_A_LEVEL\n")
    with pytest.raises(ConfigurationError, match="log_level"):
        Settings.load(config_dir=tmp_path)


def test_unknown_keys_rejected(tmp_path) -> None:
    (tmp_path / "default.yaml").write_text("app:\n  env: dev\n")
    (tmp_path / "default.yaml").write_text("unexpected_section: 1\napp:\n  env: dev\n")
    with pytest.raises(ConfigurationError):
        Settings.load(config_dir=tmp_path)
