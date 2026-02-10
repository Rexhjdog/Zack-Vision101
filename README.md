# Pokemon/One Piece TCG Stock Alert Bot

A Discord bot that monitors Melbourne-area retailers for Pokemon and One Piece TCG **booster box** stock availability and sends real-time alerts.

## Features

- **Real-time Monitoring**: Checks 5 major Melbourne retailers every 2 minutes
- **Smart Alerts**: Only notifies when items come BACK in stock (5-minute cooldown prevents spam)
- **Multiple Retailers**: EB Games, JB Hi-Fi, Target, Big W, Kmart
- **Discord Integration**: Slash commands for easy management
- **Stock History**: Tracks price changes and availability over time with automatic cleanup
- **Booster Box Focus**: Monitors only booster boxes (excludes packs, blisters, etc.)
- **Concurrent Checking**: All retailers are checked simultaneously for faster results
- **User Preferences**: Per-user alert toggle persisted to database

## Quick Start

### 1. Clone and Setup

```bash
git clone https://github.com/Rexhjdog/Zack-Vision101.git
cd Zack-Vision101
python setup.py
```

The setup script will:
- Check Python version (3.8+ required)
- Install dependencies
- Create your `.env` file
- Initialize the database

### 2. Create Discord Bot

1. Go to https://discord.com/developers/applications
2. Click "New Application" and name it
3. Go to "Bot" tab and click "Add Bot"
4. Copy the bot token
5. Under "OAuth2" > "URL Generator":
   - Select `bot` and `applications.commands` scopes
   - Select permissions: `Send Messages`, `Embed Links`, `Mention Everyone`, `Use Slash Commands`
   - Copy the generated URL and open it to invite the bot to your server

### 3. Get Channel ID

1. In Discord, enable Developer Mode (User Settings > Advanced)
2. Right-click your alert channel
3. Click "Copy Channel ID"

### 4. Run the Bot

```bash
python bot.py
```

## Discord Commands

| Command | Description |
|---------|-------------|
| `/track <url> [name]` | Add a product URL to monitor |
| `/list` | Show all tracked products |
| `/remove <id>` | Remove a product from tracking |
| `/status [retailer]` | Check current stock status |
| `/alerts <on/off>` | Toggle stock alerts for your account |
| `/force_check` | Force immediate stock check (Admin only) |
| `/help_bot` | Show help information |

## Monitored Retailers

- **EB Games** - Major gaming retailer with Pokemon/One Piece stock
- **JB Hi-Fi** - Electronics and gaming store
- **Target** - Department store with TCG sections
- **Big W** - Discount department store
- **Kmart** - Budget-friendly option

## Configuration

Edit `config.py` to customize:

```python
CHECK_INTERVAL = 120           # Check every 2 minutes
ALERT_COOLDOWN = 300           # 5 min cooldown between alerts
MAX_EMBED_FIELDS = 10          # Max products in one embed
STOCK_HISTORY_RETENTION_DAYS = 30  # Auto-cleanup history
REQUEST_DELAY_MIN = 3.0        # Rate limiting (min seconds between requests)
REQUEST_DELAY_MAX = 7.0        # Rate limiting (max seconds between requests)
```

## Architecture

```
Zack-Vision101/
├── bot.py              # Discord bot, slash commands, alert sending
├── scheduler.py        # Stock monitoring scheduler (concurrent checks)
├── database.py         # SQLite database with WAL mode and indexes
├── config.py           # All configuration constants
├── models.py           # Data models (Product, StockAlert, TrackedProduct, UserPreference)
├── scrapers/           # Retailer scrapers (selector-based)
│   ├── base.py        # Base scraper: HTTP, parsing, rate limiting, retry logic
│   ├── eb_games.py    # EB Games selectors
│   ├── jb_hifi.py     # JB Hi-Fi selectors
│   ├── target_au.py   # Target Australia selectors
│   ├── big_w.py       # Big W selectors
│   └── kmart.py       # Kmart selectors
├── requirements.txt    # Python dependencies
├── setup.py           # Interactive setup script
├── .env.example       # Environment file template
├── .gitignore         # Git ignore rules
└── LICENSE            # MIT License
```

### Key Design Decisions

- **Selector-based scrapers**: Each retailer scraper only defines CSS selectors. All fetch/parse/retry logic lives in `BaseScraper`, eliminating code duplication.
- **Callback-based alerts**: The scheduler receives an `alert_callback` function instead of importing from `bot.py`, eliminating circular imports.
- **Deterministic IDs**: Product IDs use `hashlib.md5` (not `hash()`) so they're stable across Python sessions.
- **WAL mode SQLite**: Uses Write-Ahead Logging for better concurrent read/write performance.
- **Concurrent retailer checks**: All 5 retailers are checked simultaneously via `asyncio.gather`.

## How It Works

1. **Scheduler** runs every 2 minutes and checks all enabled retailers concurrently
2. **Scrapers** fetch search pages and parse product data using retailer-specific CSS selectors
3. **Database** tracks stock history to detect changes (with automatic 30-day cleanup)
4. **Alerts** are sent when an item comes back in stock or its price changes
5. **Discord bot** provides slash commands to interact with the system

## Important Notes

- CSS selectors in each scraper are best-effort placeholders. They need to be verified against the actual retailer HTML and updated accordingly. Many modern retailer sites use JavaScript rendering, which BeautifulSoup cannot handle.
- The bot respects rate limits with 3-7 second randomized delays between requests and exponential backoff on failures.
- Stock history older than 30 days is automatically cleaned up.

## Troubleshooting

### Bot won't start
- Check that `.env` file exists and has valid token
- Ensure Python 3.8+ is installed
- Run `pip install -r requirements.txt` again

### No alerts received
- Verify bot has correct channel permissions
- Check that the bot is in your Discord server
- Look at `bot.log` for errors

### Scraper returns 0 products
- CSS selectors may not match the retailer's current HTML structure
- The retailer may use JavaScript rendering (not supported by BeautifulSoup)
- Check `bot.log` for selector mismatch warnings

## License

MIT License - See LICENSE file

## Disclaimer

This bot is for educational purposes. Always respect retailers' Terms of Service and robots.txt files. Use responsibly and don't overload websites with requests.
