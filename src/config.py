"""Configuration loaded from environment variables."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# --- Discord ---
DISCORD_TOKEN: str = os.getenv("DISCORD_TOKEN", "")
DISCORD_CHANNEL_ID: int = int(os.getenv("DISCORD_CHANNEL_ID", "0"))

# --- Scheduling ---
CHECK_INTERVAL: int = int(os.getenv("CHECK_INTERVAL", "120"))
ALERT_COOLDOWN: int = int(os.getenv("ALERT_COOLDOWN", "300"))

# --- Database ---
DATABASE_PATH: str = os.getenv("DATABASE_PATH", "data/stock_alerts.db")
DATABASE_WAL_MODE: bool = os.getenv("DATABASE_WAL_MODE", "true").lower() == "true"
HISTORY_RETENTION_DAYS: int = int(os.getenv("HISTORY_RETENTION_DAYS", "30"))

# --- HTTP ---
REQUEST_DELAY_MIN: float = float(os.getenv("REQUEST_DELAY_MIN", "3"))
REQUEST_DELAY_MAX: float = float(os.getenv("REQUEST_DELAY_MAX", "7"))
REQUEST_TIMEOUT: int = int(os.getenv("REQUEST_TIMEOUT", "30"))
MAX_RETRIES: int = int(os.getenv("MAX_RETRIES", "3"))

# --- Logging ---
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
LOG_DIR: str = os.getenv("LOG_DIR", "logs")

# --- Circuit breaker ---
CIRCUIT_BREAKER_THRESHOLD: int = int(os.getenv("CIRCUIT_BREAKER_THRESHOLD", "5"))
CIRCUIT_BREAKER_TIMEOUT: int = int(os.getenv("CIRCUIT_BREAKER_TIMEOUT", "300"))

# --- User-agent pool ---
USER_AGENTS: list[str] = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
]

# --- Booster-box filtering ---
BOOSTER_BOX_KEYWORDS: list[str] = [
    "booster box",
    "booster display",
    "booster case",
    "display box",
    "sealed box",
    "box 36",
    "box 24",
]

EXCLUSION_KEYWORDS: list[str] = [
    "single",
    "sleeve",
    "binder",
    "playmat",
    "deck box",
    "card protector",
    "top loader",
    "graded",
    "psa",
    "cgc",
    "tin",
    "blister",
    "promo",
]

# --- TCG sets ---
POKEMON_SETS: list[str] = [
    "Paldean Fates",
    "Temporal Forces",
    "Twilight Masquerade",
    "Shrouded Fable",
    "Stellar Crown",
    "Surging Sparks",
    "Prismatic Evolutions",
    "Scarlet & Violet",
    "Obsidian Flames",
    "Paldea Evolved",
    "151",
    "Paradox Rift",
    "Crown Zenith",
    "Silver Tempest",
    "Lost Origin",
    "Astral Radiance",
    "Brilliant Stars",
    "Evolving Skies",
    "Chilling Reign",
    "Battle Styles",
    "Vivid Voltage",
    "Darkness Ablaze",
    "Rebel Clash",
    "Sword & Shield",
    "Journey Together",
]

ONE_PIECE_SETS: list[str] = [
    "Romance Dawn",
    "Paramount War",
    "Pillars of Strength",
    "Kingdoms of Intrigue",
    "Awakening of the New Era",
    "Wings of the Captain",
    "500 Years in the Future",
    "Two Legends",
    "The Four Emperors",
    "Royal Blood",
    "Memorial Collection",
]

# --- Retailer definitions ---
RETAILERS: dict[str, dict] = {
    "eb_games": {
        "name": "EB Games",
        "base_url": "https://www.ebgames.com.au",
        "search_paths": {
            "pokemon": "/search?q=pokemon+booster+box",
            "one_piece": "/search?q=one+piece+booster+box",
        },
    },
    "jb_hifi": {
        "name": "JB Hi-Fi",
        "base_url": "https://www.jbhifi.com.au",
        "search_paths": {
            "pokemon": "/search?q=pokemon+booster+box&category=games",
            "one_piece": "/search?q=one+piece+booster+box&category=games",
        },
    },
    "target_au": {
        "name": "Target",
        "base_url": "https://www.target.com.au",
        "search_paths": {
            "pokemon": "/search?q=pokemon+booster+box",
            "one_piece": "/search?q=one+piece+booster+box",
        },
    },
    "big_w": {
        "name": "Big W",
        "base_url": "https://www.bigw.com.au",
        "search_paths": {
            "pokemon": "/search?q=pokemon+booster+box",
            "one_piece": "/search?q=one+piece+booster+box",
        },
    },
    "kmart": {
        "name": "Kmart",
        "base_url": "https://www.kmart.com.au",
        "search_paths": {
            "pokemon": "/search?q=pokemon+booster+box",
            "one_piece": "/search?q=one+piece+booster+box",
        },
    },
}

ALLOWED_DOMAINS: set[str] = {cfg["base_url"].split("//")[1] for cfg in RETAILERS.values()}


def data_dir() -> Path:
    """Return (and create) the data directory."""
    p = Path(DATABASE_PATH).parent
    p.mkdir(parents=True, exist_ok=True)
    return p
