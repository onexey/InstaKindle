"""Configuration management for InstaKindle.

Loads settings from environment variables with CLI argument overrides.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field, fields
from typing import Any

logger = logging.getLogger(__name__)

# Mapping from env var name to config field name
_ENV_MAP: dict[str, str] = {
    "INSTAPAPER_KEY": "instapaper_key",
    "INSTAPAPER_SECRET": "instapaper_secret",
    "INSTAPAPER_USERNAME": "instapaper_username",
    "INSTAPAPER_PASSWORD": "instapaper_password",
    "KINDLE_EMAIL": "kindle_email",
    "SMTP_HOST": "smtp_host",
    "SMTP_PORT": "smtp_port",
    "SMTP_USERNAME": "smtp_username",
    "SMTP_PASSWORD": "smtp_password",
    "SENDER_EMAIL": "sender_email",
    "POLL_INTERVAL": "poll_interval",
    "LOG_LEVEL": "log_level",
    "CONVERTER": "converter",
}


@dataclass(frozen=True)
class Config:
    """Application configuration.

    All required fields must be provided either via environment variables
    or CLI arguments. Optional fields have sensible defaults.
    """

    # Instapaper OAuth credentials
    instapaper_key: str = ""
    instapaper_secret: str = ""
    instapaper_username: str = ""
    instapaper_password: str = ""

    # Kindle delivery
    kindle_email: str = ""

    # SMTP settings
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    sender_email: str = ""

    # Polling & runtime
    poll_interval: int = 900
    log_level: str = "info"

    # Converter engine: "calibre", "pandoc", or "ebooklib"
    converter: str = "ebooklib"

    # Required fields that must be non-empty
    _required_fields: tuple[str, ...] = field(
        default=(
            "instapaper_key",
            "instapaper_secret",
            "instapaper_username",
            "instapaper_password",
            "kindle_email",
            "smtp_host",
            "smtp_username",
            "smtp_password",
            "sender_email",
        ),
        repr=False,
        compare=False,
    )

    def validate(self) -> list[str]:
        """Validate configuration and return list of error messages."""
        errors: list[str] = []

        for field_name in self._required_fields:
            value = getattr(self, field_name)
            if not value:
                env_name = next(
                    (k for k, v in _ENV_MAP.items() if v == field_name), field_name.upper()
                )
                errors.append(f"Missing required configuration: {env_name}")

        if self.smtp_port < 1 or self.smtp_port > 65535:
            errors.append(f"Invalid SMTP port: {self.smtp_port}")

        if self.poll_interval < 1:
            errors.append(f"Invalid poll interval: {self.poll_interval}")

        valid_converters = {"calibre", "pandoc", "ebooklib"}
        if self.converter not in valid_converters:
            errors.append(
                f"Invalid converter '{self.converter}'. Must be one of: {valid_converters}"
            )

        valid_levels = {"debug", "info", "warn", "warning", "error", "critical"}
        if self.log_level.lower() not in valid_levels:
            errors.append(f"Invalid log level '{self.log_level}'")

        return errors

    @property
    def log_level_int(self) -> int:
        """Return the numeric log level."""
        level_map = {
            "debug": logging.DEBUG,
            "info": logging.INFO,
            "warn": logging.WARNING,
            "warning": logging.WARNING,
            "error": logging.ERROR,
            "critical": logging.CRITICAL,
        }
        return level_map.get(self.log_level.lower(), logging.INFO)


def load_config(cli_overrides: dict[str, Any] | None = None) -> Config:
    """Load configuration from environment variables with optional CLI overrides.

    Priority: CLI arguments > environment variables > defaults.
    """
    kwargs: dict[str, Any] = {}

    # Load from environment
    for env_name, field_name in _ENV_MAP.items():
        env_value = os.environ.get(env_name)
        if env_value is not None:
            kwargs[field_name] = env_value

    # Apply CLI overrides (only non-None values)
    if cli_overrides:
        for key, value in cli_overrides.items():
            if value is not None:
                kwargs[key] = value

    # Type coercion for int fields
    int_fields = {f.name for f in fields(Config) if f.type == "int" and not f.name.startswith("_")}
    for field_name in int_fields:
        if field_name in kwargs and isinstance(kwargs[field_name], str):
            try:
                kwargs[field_name] = int(kwargs[field_name])
            except ValueError:
                logger.warning("Invalid integer value for %s: %s", field_name, kwargs[field_name])

    # Remove internal fields
    kwargs.pop("_required_fields", None)

    return Config(**kwargs)
