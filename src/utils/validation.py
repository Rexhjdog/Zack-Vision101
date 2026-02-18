"""Startup configuration validation."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from src.config import (
    ALERT_COOLDOWN,
    CHECK_INTERVAL,
    DISCORD_CHANNEL_ID,
    DISCORD_TOKEN,
    REQUEST_DELAY_MAX,
    REQUEST_DELAY_MIN,
    RETAILERS,
)

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    valid: bool
    errors: list[str]
    warnings: list[str]


def validate_config() -> ValidationResult:
    """Check that all required configuration is present and sane."""
    errors: list[str] = []
    warnings: list[str] = []

    # Required values
    if not DISCORD_TOKEN:
        errors.append("DISCORD_TOKEN is not set")
    if DISCORD_CHANNEL_ID == 0:
        errors.append("DISCORD_CHANNEL_ID is not set or is 0")

    # Numeric ranges
    if CHECK_INTERVAL < 30:
        warnings.append(
            f"CHECK_INTERVAL={CHECK_INTERVAL}s is very aggressive, may trigger rate limits"
        )
    if ALERT_COOLDOWN < 60:
        warnings.append(
            f"ALERT_COOLDOWN={ALERT_COOLDOWN}s is very short, may cause duplicate alerts"
        )
    if REQUEST_DELAY_MIN >= REQUEST_DELAY_MAX:
        warnings.append("REQUEST_DELAY_MIN should be less than REQUEST_DELAY_MAX")
    if REQUEST_DELAY_MIN < 1:
        warnings.append("REQUEST_DELAY_MIN < 1s risks rate limiting")

    # Retailers
    if not RETAILERS:
        errors.append("No retailers configured")

    for key, cfg in RETAILERS.items():
        if "base_url" not in cfg:
            errors.append(f"Retailer '{key}' missing base_url")
        if "search_paths" not in cfg or not cfg["search_paths"]:
            warnings.append(f"Retailer '{key}' has no search_paths")

    result = ValidationResult(
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
    )

    if errors:
        for e in errors:
            logger.error("Config error: %s", e)
    for w in warnings:
        logger.warning("Config warning: %s", w)

    return result
