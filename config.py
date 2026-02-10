import os
from dotenv import load_dotenv

load_dotenv()

# Discord Configuration
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
DISCORD_CHANNEL_ID = int(os.getenv('DISCORD_CHANNEL_ID', 0))

# Check Interval (seconds)
CHECK_INTERVAL = 120  # 2 minutes

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

# High Rarity Keywords
HIGH_RARITY_KEYWORDS = [
    'secret rare',
    'alternate art',
    'alt art',
    'full art',
    'rainbow rare',
    'gold',
    'hyper rare',
    'special illustration',
    'character rare',
    'parallel',
    'foil',
    'holo',
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

# Retailer URLs to Monitor
RETAILERS = {
    'eb_games': {
        'name': 'EB Games',
        'base_url': 'https://www.ebgames.com.au',
        'search_urls': [
            'https://www.ebgames.com.au/search?q=pokemon+booster+box',
            'https://www.ebgames.com.au/search?q=one+piece+booster+box',
        ],
        'enabled': True,
    },
    'jb_hifi': {
        'name': 'JB Hi-Fi',
        'base_url': 'https://www.jbhifi.com.au',
        'search_urls': [
            'https://www.jbhifi.com.au/search?page=1&query=pokemon%20booster%20box',
            'https://www.jbhifi.com.au/search?page=1&query=one%20piece%20booster%20box',
        ],
        'enabled': True,
    },
    'target': {
        'name': 'Target Australia',
        'base_url': 'https://www.target.com.au',
        'search_urls': [
            'https://www.target.com.au/search?text=pokemon+booster+box',
            'https://www.target.com.au/search?text=one+piece+booster+box',
        ],
        'enabled': True,
    },
    'big_w': {
        'name': 'Big W',
        'base_url': 'https://www.bigw.com.au',
        'search_urls': [
            'https://www.bigw.com.au/search?q=pokemon+booster+box',
            'https://www.bigw.com.au/search?q=one+piece+booster+box',
        ],
        'enabled': True,
    },
    'kmart': {
        'name': 'Kmart Australia',
        'base_url': 'https://www.kmart.com.au',
        'search_urls': [
            'https://www.kmart.com.au/search/?q=pokemon+booster+box',
            'https://www.kmart.com.au/search/?q=one+piece+booster+box',
        ],
        'enabled': True,
    },
}

# Database
DATABASE_PATH = 'stock_alerts.db'

# Alert Settings
ALERT_COOLDOWN = 300  # 5 minutes between alerts for same product
MAX_ALERTS_PER_HOUR = 50  # Rate limiting

# Rate Limiting Settings
REQUEST_DELAY_MIN = 3.0  # Minimum seconds between requests to same retailer
REQUEST_DELAY_MAX = 7.0  # Maximum seconds between requests (randomized)
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
