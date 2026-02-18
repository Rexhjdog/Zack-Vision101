"""Logging setup with rotating file handlers."""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from src.config import LOG_DIR, LOG_LEVEL


def setup_logging() -> None:
    """Configure root logger with console + rotating file output."""
    log_dir = Path(LOG_DIR)
    log_dir.mkdir(parents=True, exist_ok=True)

    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)

    # File handler (10 MB, keep 5 backups)
    file_handler = RotatingFileHandler(
        log_dir / "zack_vision.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(fmt)

    root = logging.getLogger()
    root.setLevel(getattr(logging, LOG_LEVEL.upper(), logging.INFO))
    root.addHandler(console)
    root.addHandler(file_handler)

    # Silence noisy third-party loggers
    for name in ("discord", "aiohttp", "aiosqlite"):
        logging.getLogger(name).setLevel(logging.WARNING)
