"""Configuration validation."""
import os
import re
import logging
from typing import List, Tuple, Optional
from urllib.parse import urlparse

from src.config import (
    DISCORD_TOKEN, DISCORD_CHANNEL_ID,
    DATABASE_PATH, RETAILERS, ALLOWED_DOMAINS
)

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Raised when configuration validation fails."""
    pass


class ConfigValidator:
    """Validates application configuration on startup."""
    
    def __init__(self):
        self.errors: List[str] = []
        self.warnings: List[str] = []
    
    def validate_all(self) -> Tuple[bool, List[str], List[str]]:
        """Run all validation checks.
        
        Returns:
            Tuple of (is_valid, errors, warnings)
        """
        self.errors = []
        self.warnings = []
        
        self._validate_discord_config()
        self._validate_database_config()
        self._validate_retailers()
        self._validate_file_paths()
        self._validate_environment()
        
        is_valid = len(self.errors) == 0
        
        if is_valid:
            logger.info("✅ Configuration validation passed")
        else:
            logger.error(f"❌ Configuration validation failed with {len(self.errors)} errors")
        
        if self.warnings:
            logger.warning(f"⚠️  Configuration has {len(self.warnings)} warnings")
        
        return is_valid, self.errors, self.warnings
    
    def _validate_discord_config(self):
        """Validate Discord configuration."""
        # Validate token
        if not DISCORD_TOKEN:
            self.errors.append("DISCORD_TOKEN is not set")
        elif len(DISCORD_TOKEN) < 50:
            self.errors.append("DISCORD_TOKEN appears to be invalid (too short)")
        elif not re.match(r'^[MN][A-Za-z\d]{23}\.[\w-]{6}\.[\w-]{27}$', DISCORD_TOKEN):
            self.warnings.append("DISCORD_TOKEN format appears unusual (should be Mxxxxx.xxxxxx.xxxxxx)")
        
        # Validate channel ID
        if not DISCORD_CHANNEL_ID:
            self.errors.append("DISCORD_CHANNEL_ID is not set")
        elif DISCORD_CHANNEL_ID == 0:
            self.errors.append("DISCORD_CHANNEL_ID is set to 0 (invalid)")
        elif not isinstance(DISCORD_CHANNEL_ID, int):
            self.errors.append("DISCORD_CHANNEL_ID must be an integer")
        elif DISCORD_CHANNEL_ID < 100000000000000000:
            self.warnings.append("DISCORD_CHANNEL_ID appears to be very small (possibly invalid)")
    
    def _validate_database_config(self):
        """Validate database configuration."""
        if not DATABASE_PATH:
            self.errors.append("DATABASE_PATH is not set")
        else:
            # Check if directory is writable
            db_dir = os.path.dirname(os.path.abspath(DATABASE_PATH))
            if db_dir and not os.path.exists(db_dir):
                try:
                    os.makedirs(db_dir, exist_ok=True)
                    logger.info(f"Created database directory: {db_dir}")
                except Exception as e:
                    self.errors.append(f"Cannot create database directory {db_dir}: {e}")
            elif db_dir and not os.access(db_dir, os.W_OK):
                self.errors.append(f"Database directory {db_dir} is not writable")
    
    def _validate_retailers(self):
        """Validate retailer configurations."""
        if not RETAILERS:
            self.errors.append("No retailers configured")
            return
        
        for key, config in RETAILERS.items():
            # Validate retailer has required fields
            if not hasattr(config, 'name') or not config.name:
                self.errors.append(f"Retailer {key}: missing name")
            
            if not hasattr(config, 'base_url') or not config.base_url:
                self.errors.append(f"Retailer {key}: missing base_url")
            else:
                # Validate URL format
                try:
                    parsed = urlparse(config.base_url)
                    if not parsed.scheme or not parsed.netloc:
                        self.errors.append(f"Retailer {key}: invalid base_url format")
                except Exception as e:
                    self.errors.append(f"Retailer {key}: invalid base_url - {e}")
            
            if not hasattr(config, 'search_urls') or not config.search_urls:
                self.errors.append(f"Retailer {key}: missing search_urls")
            else:
                # Validate each search URL
                for i, url in enumerate(config.search_urls):
                    try:
                        parsed = urlparse(url)
                        if not parsed.scheme or not parsed.netloc:
                            self.errors.append(f"Retailer {key}: invalid search_url[{i}]")
                    except Exception as e:
                        self.errors.append(f"Retailer {key}: invalid search_url[{i}] - {e}")
            
            # Check if enabled
            if hasattr(config, 'enabled') and not config.enabled:
                self.warnings.append(f"Retailer {key} is disabled")
    
    def _validate_file_paths(self):
        """Validate file and directory paths."""
        # Check logs directory
        log_dir = os.path.dirname(os.path.abspath(os.getenv('LOG_FILE', 'logs/bot.log')))
        if log_dir and not os.path.exists(log_dir):
            try:
                os.makedirs(log_dir, exist_ok=True)
                logger.info(f"Created logs directory: {log_dir}")
            except Exception as e:
                self.warnings.append(f"Cannot create logs directory: {e}")
        
        # Check data directory
        data_dir = os.path.dirname(os.path.abspath(DATABASE_PATH))
        if data_dir and not os.path.exists(data_dir):
            try:
                os.makedirs(data_dir, exist_ok=True)
                logger.info(f"Created data directory: {data_dir}")
            except Exception as e:
                self.errors.append(f"Cannot create data directory: {e}")
    
    def _validate_environment(self):
        """Validate environment settings."""
        # Check Python version
        import sys
        if sys.version_info < (3, 8):
            self.errors.append(f"Python {sys.version_info.major}.{sys.version_info.minor} is not supported. Minimum is 3.8")
        elif sys.version_info < (3, 10):
            self.warnings.append(f"Python {sys.version_info.major}.{sys.version_info.minor} is supported but 3.10+ is recommended")
        
        # Check for required environment variables
        required_env = ['DISCORD_TOKEN', 'DISCORD_CHANNEL_ID']
        for env_var in required_env:
            if not os.getenv(env_var):
                self.errors.append(f"Environment variable {env_var} is not set")
        
        # Validate check interval
        check_interval = int(os.getenv('CHECK_INTERVAL', '120'))
        if check_interval < 60:
            self.warnings.append(f"CHECK_INTERVAL ({check_interval}s) is very short. This may cause rate limiting.")
        elif check_interval > 1800:
            self.warnings.append(f"CHECK_INTERVAL ({check_interval}s) is very long. You may miss stock updates.")
        
        # Validate alert cooldown
        alert_cooldown = int(os.getenv('ALERT_COOLDOWN', '300'))
        if alert_cooldown < 60:
            self.warnings.append(f"ALERT_COOLDOWN ({alert_cooldown}s) is very short. This may cause alert spam.")


def validate_config() -> bool:
    """Validate configuration and exit if invalid.
    
    Returns:
        bool: True if configuration is valid
        
    Raises:
        ValidationError: If configuration is invalid
    """
    validator = ConfigValidator()
    is_valid, errors, warnings = validator.validate_all()
    
    if not is_valid:
        logger.error("=" * 60)
        logger.error("CONFIGURATION VALIDATION FAILED")
        logger.error("=" * 60)
        for i, error in enumerate(errors, 1):
            logger.error(f"  {i}. {error}")
        logger.error("=" * 60)
        logger.error("Please fix the above errors and restart the bot.")
        raise ValidationError(f"Configuration validation failed: {len(errors)} errors")
    
    if warnings:
        logger.warning("Configuration warnings:")
        for warning in warnings:
            logger.warning(f"  - {warning}")
    
    return True
