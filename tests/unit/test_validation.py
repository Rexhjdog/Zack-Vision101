"""Tests for configuration validation."""

import os
from unittest import mock

from src.utils.validation import validate_config


class TestValidation:
    def test_valid_config(self):
        result = validate_config()
        # With the defaults set in conftest, token and channel are set
        assert result.valid is True

    def test_missing_token(self):
        with mock.patch("src.utils.validation.DISCORD_TOKEN", ""):
            result = validate_config()
            assert result.valid is False
            assert any("DISCORD_TOKEN" in e for e in result.errors)

    def test_missing_channel(self):
        with mock.patch("src.utils.validation.DISCORD_CHANNEL_ID", 0):
            result = validate_config()
            assert result.valid is False
            assert any("DISCORD_CHANNEL_ID" in e for e in result.errors)

    def test_aggressive_interval_warning(self):
        with mock.patch("src.utils.validation.CHECK_INTERVAL", 10):
            result = validate_config()
            assert any("aggressive" in w for w in result.warnings)
