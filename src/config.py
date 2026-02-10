"""Configuration management for Zack Vision."""
import os
from dataclasses import dataclass
from typing import List, Dict
from dotenv import load_dotenv

load_dotenv()


@dataclass
class RetailerConfig:
    """Configuration for a retailer."""
    name: str
    base_url: str
    search_urls: List[str]
    enabled: bool = True


# Discord Configuration
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
DISCORD_CHANNEL_ID = int(os.getenv('DISCORD_CHANNEL_ID', 0))

# Monitoring Configuration
CHECK_INTERVAL = int(os.getenv('CHECK_INTERVAL', '120'))  # 2 minutes default
ALERT_COOLDOWN = int(os.getenv('ALERT_COOLDOWN', '300'))  # 5 minutes default
MAX_ALERTS_PER_HOUR = int(os.getenv('MAX_ALERTS_PER_HOUR', '50'))

# Database Configuration
DATABASE_PATH = os.getenv('DATABASE_PATH', 'data/stock_alerts.db')
DATABASE_WAL_MODE = True  # Write-Ahead Logging for better concurrency

# Request Configuration
REQUEST_DELAY_MIN = float(os.getenv('REQUEST_DELAY_MIN', '3.0'))
REQUEST_DELAY_MAX = float(os.getenv('REQUEST_DELAY_MAX', '7.0'))
RETRY_ATTEMPTS = int(os.getenv('RETRY_ATTEMPTS', '3'))
RETRY_DELAY_BASE = int(os.getenv('RETRY_DELAY_BASE', '2'))
REQUEST_TIMEOUT = int(os.getenv('REQUEST_TIMEOUT', '30'))

# Product Filtering
BOOSTER_BOX_KEYWORDS = [
    'booster box',
    'booster display',
    'display box',
    'case',
    'carton',
    '36 pack',
    '24 pack',
    'booster case',
]

EXCLUDE_KEYWORDS = [
    'booster pack', 'blister', '3-pack', '6-pack', '10-pack',
    'single pack', 'booster sleeve', 'sleeve', 'binder',
    'playmat', 'deck box', 'card sleeves', 'elite trainer box',
    'etb', 'tin', 'collection box',
]

# TCG Sets
POKEMON_SETS = [
    'Paldean Fates', 'Temporal Forces', 'Twilight Masquerade',
    'Shrouded Fable', 'Stellar Crown', 'Surging Sparks',
    'Prismatic Evolutions', 'Journey Together', '151',
    'Obsidian Flames', 'Paradox Rift',
]

ONE_PIECE_SETS = [
    'Romance Dawn', 'Paramount War', 'Pillars of Strength',
    'Kingdoms of Intrigue', 'Awakening of the New Era',
    'Wings of the Captain', '500 Years in the Future',
    'Two Legends', 'Emperors in the New World',
    'Royal Blood', 'The Skypiea',
]

# Retailer Configurations
RETAILERS: Dict[str, RetailerConfig] = {
    'eb_games': RetailerConfig(
        name='EB Games',
        base_url='https://www.ebgames.com.au',
        search_urls=[
            'https://www.ebgames.com.au/search?q=pokemon+booster+box',
            'https://www.ebgames.com.au/search?q=one+piece+booster+box',
        ]
    ),
    'jb_hifi': RetailerConfig(
        name='JB Hi-Fi',
        base_url='https://www.jbhifi.com.au',
        search_urls=[
            'https://www.jbhifi.com.au/search?page=1&query=pokemon%20booster%20box',
            'https://www.jbhifi.com.au/search?page=1&query=one%20piece%20booster%20box',
        ]
    ),
    'target': RetailerConfig(
        name='Target Australia',
        base_url='https://www.target.com.au',
        search_urls=[
            'https://www.target.com.au/search?text=pokemon+booster+box',
            'https://www.target.com.au/search?text=one+piece+booster+box',
        ]
    ),
    'big_w': RetailerConfig(
        name='Big W',
        base_url='https://www.bigw.com.au',
        search_urls=[
            'https://www.bigw.com.au/search?q=pokemon+booster+box',
            'https://www.bigw.com.au/search?q=one+piece+booster+box',
        ]
    ),
    'kmart': RetailerConfig(
        name='Kmart Australia',
        base_url='https://www.kmart.com.au',
        search_urls=[
            'https://www.kmart.com.au/search/?q=pokemon+booster+box',
            'https://www.kmart.com.au/search/?q=one+piece+booster+box',
        ]
    ),
}

# Allowed domains for URL validation
ALLOWED_DOMAINS = [
    'ebgames.com.au',
    'jbhifi.com.au',
    'target.com.au',
    'bigw.com.au',
    'kmart.com.au',
    'www.ebgames.com.au',
    'www.jbhifi.com.au',
    'www.target.com.au',
    'www.bigw.com.au',
    'www.kmart.com.au',
]

# User Agents for rotation
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
]

# Logging Configuration
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
LOG_FILE = os.getenv('LOG_FILE', 'logs/bot.log')
