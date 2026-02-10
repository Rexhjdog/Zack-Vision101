import os
from dotenv import load_dotenv

load_dotenv()

# Discord Configuration
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
DISCORD_CHANNEL_ID = int(os.getenv('DISCORD_CHANNEL_ID', 0))

# Check Interval (seconds)
CHECK_INTERVAL = 120  # 2 minutes
ERROR_RETRY_INTERVAL = 60  # 1 minute after errors

# Booster Box Keywords ONLY - we only track boxes, not packs
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

# Exclude keywords - booster packs and non-TCG items
EXCLUDE_KEYWORDS = [
    'booster pack', 'blister', '3-pack', '6-pack', '10-pack',
    'single pack', 'booster sleeve', 'sleeve', 'binder',
    'playmat', 'deck box', 'card sleeves', 'elite trainer box',
]

# Pokemon Sets to Track (current high-value sets)
POKEMON_SETS = [
    'Paldean Fates',
    'Temporal Forces',
    'Twilight Masquerade',
    'Shrouded Fable',
    'Stellar Crown',
    'Surging Sparks',
    'Prismatic Evolutions',
    'Journey Together',
    '151',
    'Obsidian Flames',
    'Paradox Rift',
]

# One Piece Sets to Track
ONE_PIECE_SETS = [
    'Romance Dawn',
    'Paramount War',
    'Pillars of Strength',
    'Kingdoms of Intrigue',
    'Awakening of the New Era',
    'Wings of the Captain',
    '500 Years in the Future',
    'Two Legends',
    'Emperors in the New World',
    'Royal Blood',
    'The Skypiea',
]

# Retailers to Monitor
RETAILERS = {
    'eb_games': {
        'name': 'EB Games',
        'base_url': 'https://www.ebgames.com.au',
        'enabled': True,
    },
    'jb_hifi': {
        'name': 'JB Hi-Fi',
        'base_url': 'https://www.jbhifi.com.au',
        'enabled': True,
    },
    'target': {
        'name': 'Target Australia',
        'base_url': 'https://www.target.com.au',
        'enabled': True,
    },
    'big_w': {
        'name': 'Big W',
        'base_url': 'https://www.bigw.com.au',
        'enabled': True,
    },
    'kmart': {
        'name': 'Kmart Australia',
        'base_url': 'https://www.kmart.com.au',
        'enabled': True,
    },
}

# Database
DATABASE_PATH = 'stock_alerts.db'

# Alert Settings
ALERT_COOLDOWN = 300  # 5 minutes between alerts for same product
MAX_EMBED_FIELDS = 10  # Max products shown in a single Discord embed
STOCK_HISTORY_RETENTION_DAYS = 30  # Auto-cleanup older history

# Rate Limiting Settings
REQUEST_DELAY_MIN = 3.0  # Minimum seconds between requests to same retailer
REQUEST_DELAY_MAX = 7.0  # Maximum seconds between requests (randomized)
REQUEST_TIMEOUT = 30  # HTTP request timeout in seconds
RETRY_ATTEMPTS = 3  # Number of retry attempts for failed requests
RETRY_DELAY_BASE = 2  # Base seconds for exponential backoff

# User Agents for rotation
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
]

# Allowed domains for URL validation
ALLOWED_DOMAINS = [
    'ebgames.com.au',
    'jbhifi.com.au',
    'target.com.au',
    'bigw.com.au',
    'kmart.com.au',
]

# Logging
LOG_FILE = 'bot.log'
