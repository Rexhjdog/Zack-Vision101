# Zack Vision - TCG Stock Alert Bot

Discord bot that monitors Australian retailers for Pokemon and One Piece TCG booster box stock and sends real-time alerts.

## Features

- **5 Retailers**: EB Games, JB Hi-Fi, Target, Big W, Kmart
- **Smart Alerts**: Notifies on stock transitions (out-of-stock → in-stock), price changes, and new listings
- **Alert Cooldown**: Configurable dedup window (default 5 min)
- **Circuit Breaker**: Graceful degradation when a retailer is down
- **Concurrent Scraping**: All retailers + categories checked simultaneously via asyncio
- **WAL-mode SQLite**: Async database with indexed queries and 30-day history retention
- **Health & Metrics**: Built-in `/health` and `/stats` commands

## Quick Start

```bash
pip install -r requirements.txt
cp .env.example .env   # then fill in DISCORD_TOKEN and DISCORD_CHANNEL_ID
python bot.py
```

### Discord Bot Setup

1. Create an app at the [Discord Developer Portal](https://discord.com/developers/applications)
2. Add a Bot, copy the token into `.env`
3. OAuth2 scopes: `bot`, `applications.commands`
4. Bot permissions: Send Messages, Embed Links, Mention Everyone

## Commands

| Command | Description |
|---------|-------------|
| `/track <url> [name]` | Add a product URL to monitor |
| `/untrack <url>` | Stop monitoring a URL |
| `/list` | Show all tracked products by retailer |
| `/status [retailer]` | Show currently in-stock items |
| `/force_check` | Trigger an immediate scrape cycle |
| `/stats` | Bot statistics (products, alerts, scheduler) |
| `/health` | Health check (Discord, DB, Scheduler) |

## Docker

```bash
docker compose up -d
```

Or build manually:

```bash
docker build -t zack-vision .
docker run -d --env-file .env -v ./data:/app/data -v ./logs:/app/logs zack-vision
```

## Configuration

All settings via environment variables (see `.env.example`):

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DISCORD_TOKEN` | Yes | — | Bot token |
| `DISCORD_CHANNEL_ID` | Yes | — | Alert channel ID |
| `CHECK_INTERVAL` | No | 120 | Seconds between scrape cycles |
| `ALERT_COOLDOWN` | No | 300 | Dedup window in seconds |
| `DATABASE_PATH` | No | `data/stock_alerts.db` | SQLite file path |
| `LOG_LEVEL` | No | INFO | Logging verbosity |
| `CIRCUIT_BREAKER_THRESHOLD` | No | 5 | Failures before opening breaker |

## Project Structure

```
src/
├── config.py              # Env-based configuration
├── main.py                # Discord bot + slash commands
├── models/
│   └── product.py         # Product, StockAlert, TrackedProduct, StockHistory
├── scrapers/
│   ├── base.py            # BaseScraper (circuit breaker, retries, rate-limit)
│   ├── eb_games.py        # EB Games AU
│   ├── jb_hifi.py         # JB Hi-Fi AU
│   ├── target_au.py       # Target AU
│   ├── big_w.py           # Big W AU
│   └── kmart.py           # Kmart AU
├── services/
│   ├── database.py        # Async SQLite (products, alerts, history, tracked)
│   └── scheduler.py       # Stock monitoring loop
└── utils/
    ├── logging_config.py  # Rotating file + console logging
    ├── metrics.py         # In-memory counters/gauges/histograms
    ├── health.py          # Component health checks
    └── validation.py      # Startup config validation
tests/
├── unit/                  # Model, scraper, validation tests
└── integration/           # Database integration tests
```

## Testing

```bash
pytest tests/ -v
```

## License

MIT
