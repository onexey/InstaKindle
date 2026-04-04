"""Tests for the configuration module."""

from __future__ import annotations

import logging
import os
from unittest.mock import patch

import pytest

from instakindle.config import Config, load_config


class TestConfig:
    """Tests for the Config dataclass."""

    def test_defaults(self) -> None:
        """Config should have sensible defaults."""
        config = Config()
        assert config.smtp_port == 587
        assert config.poll_interval == 900
        assert config.log_level == "info"
        assert config.converter == "ebooklib"

    def test_validate_missing_required(self) -> None:
        """Validation should report missing required fields."""
        config = Config()
        errors = config.validate()
        assert len(errors) > 0
        assert any("INSTAPAPER_KEY" in e for e in errors)
        assert any("KINDLE_EMAIL" in e for e in errors)

    def test_validate_valid_config(self, sample_config: Config) -> None:
        """A fully populated config should pass validation."""
        errors = sample_config.validate()
        assert errors == []

    def test_validate_invalid_port(self, sample_config: Config) -> None:
        """Validation should catch invalid port numbers."""
        config = Config(
            **{
                **{k: v for k, v in vars(sample_config).items() if not k.startswith("_")},
                "smtp_port": 0,
            }
        )
        errors = config.validate()
        assert any("port" in e.lower() for e in errors)

    def test_validate_invalid_converter(self, sample_config: Config) -> None:
        """Validation should catch invalid converter names."""
        config = Config(
            **{
                **{k: v for k, v in vars(sample_config).items() if not k.startswith("_")},
                "converter": "nonexistent",
            }
        )
        errors = config.validate()
        assert any("converter" in e.lower() for e in errors)

    def test_validate_invalid_log_level(self, sample_config: Config) -> None:
        """Validation should catch invalid log levels."""
        config = Config(
            **{
                **{k: v for k, v in vars(sample_config).items() if not k.startswith("_")},
                "log_level": "verbose",
            }
        )
        errors = config.validate()
        assert any("log level" in e.lower() for e in errors)

    def test_validate_negative_poll_interval(self, sample_config: Config) -> None:
        """Validation should catch negative poll intervals."""
        config = Config(
            **{
                **{k: v for k, v in vars(sample_config).items() if not k.startswith("_")},
                "poll_interval": -1,
            }
        )
        errors = config.validate()
        assert any("poll interval" in e.lower() for e in errors)

    def test_log_level_int(self) -> None:
        """log_level_int should return correct numeric level."""
        assert Config(log_level="debug").log_level_int == logging.DEBUG
        assert Config(log_level="info").log_level_int == logging.INFO
        assert Config(log_level="warn").log_level_int == logging.WARNING
        assert Config(log_level="error").log_level_int == logging.ERROR

    def test_frozen(self, sample_config: Config) -> None:
        """Config should be immutable (frozen dataclass)."""
        with pytest.raises(AttributeError):
            sample_config.smtp_port = 465  # type: ignore[misc]


class TestLoadConfig:
    """Tests for load_config function."""

    def test_load_from_env(self) -> None:
        """Should load configuration from environment variables."""
        env = {
            "INSTAPAPER_KEY": "env_key",
            "INSTAPAPER_SECRET": "env_secret",
            "INSTAPAPER_USERNAME": "env_user",
            "INSTAPAPER_PASSWORD": "env_pass",
            "KINDLE_EMAIL": "me@kindle.com",
            "SMTP_HOST": "smtp.test.com",
            "SMTP_PORT": "465",
            "SMTP_USERNAME": "smtp_user",
            "SMTP_PASSWORD": "smtp_pass",
            "SENDER_EMAIL": "from@test.com",
            "POLL_INTERVAL": "120",
            "LOG_LEVEL": "debug",
        }
        with patch.dict(os.environ, env, clear=False):
            config = load_config()

        assert config.instapaper_key == "env_key"
        assert config.smtp_port == 465
        assert config.poll_interval == 120
        assert config.log_level == "debug"

    def test_cli_overrides_env(self) -> None:
        """CLI arguments should override environment variables."""
        env = {"INSTAPAPER_KEY": "env_key"}
        cli = {"instapaper_key": "cli_key"}

        with patch.dict(os.environ, env, clear=False):
            config = load_config(cli_overrides=cli)

        assert config.instapaper_key == "cli_key"

    def test_cli_none_values_ignored(self) -> None:
        """None CLI values should not override env/defaults."""
        env = {"INSTAPAPER_KEY": "env_key"}
        cli = {"instapaper_key": None, "instapaper_secret": "cli_secret"}

        with patch.dict(os.environ, env, clear=False):
            config = load_config(cli_overrides=cli)

        assert config.instapaper_key == "env_key"
        assert config.instapaper_secret == "cli_secret"

    def test_defaults_used_when_nothing_set(self) -> None:
        """Default values should be used when neither env nor CLI provide a value."""
        with patch.dict(os.environ, {}, clear=True):
            config = load_config()
        assert config.smtp_port == 587
        assert config.poll_interval == 900

    def test_int_coercion_from_env(self) -> None:
        """String values from env should be coerced to int for int fields."""
        env = {"SMTP_PORT": "2525", "POLL_INTERVAL": "300"}
        with patch.dict(os.environ, env, clear=False):
            config = load_config()
        assert config.smtp_port == 2525
        assert config.poll_interval == 300

    def test_converter_env_var(self) -> None:
        """CONVERTER env var should set the converter field."""
        env = {"CONVERTER": "pandoc"}
        with patch.dict(os.environ, env, clear=False):
            config = load_config()
        assert config.converter == "pandoc"
