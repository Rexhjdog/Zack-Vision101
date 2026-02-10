# 🎴 Zack Vision - TCG Stock Alert Bot

A Discord bot that monitors Australian retailers for Pokémon and One Piece TCG booster box stock and sends real-time alerts.

## Features

- **5 Major Retailers**: EB Games, JB Hi-Fi, Target, Big W, Kmart
- **Smart Alerts**: Only notifies when items come back in stock
- **5-Minute Cooldown**: Prevents alert spam
- **Circuit Breaker**: Handles retailer failures gracefully
- **Concurrent Checks**: All retailers checked simultaneously
- **WAL Mode SQLite**: Better performance with concurrent reads/writes

## Quick Start

### 1. Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Copy and configure environment
cp .env.example .env
# Edit .env with your Discord token and channel ID
```

### 2. Discord Bot Setup

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Create New Application → Bot → Add Bot
3. Copy the Token
4. Enable OAuth2 scopes: `bot`, `applications.commands`
5. Enable permissions: Send Messages, Embed Links, Mention @everyone

### 3. Run

```bash
python bot.py
```

## Commands

- `/track <url> [name]` - Add a product to monitor
- `/list` - Show all tracked products
- `/status [retailer]` - Check current stock status
- `/force_check` - Force immediate stock check
- `/stats` - Show bot statistics

## Docker

```bash
docker build -t zack-vision .
docker run -d --env-file .env --name zack-vision zack-vision
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DISCORD_TOKEN` | ✅ | Bot token from Discord Developer Portal |
| `DISCORD_CHANNEL_ID` | ✅ | Channel ID for alerts |
| `CHECK_INTERVAL` | ❌ | Check interval in seconds (default: 120) |
| `ALERT_COOLDOWN` | ❌ | Alert cooldown in seconds (default: 300) |

## Architecture

```
src/
├── config.py          # Configuration management
├── models/            # Data models
│   └── product.py
├── scrapers/          # Retailer scrapers
│   ├── base.py       # Base scraper with circuit breaker
│   ├── eb_games.py
│   ├── jb_hifi.py
│   ├── target_au.py
│   ├── big_w.py
│   └── kmart.py
├── services/          # Business logic
│   ├── database.py   # Async SQLite operations
│   └── scheduler.py  # Stock monitoring
└── main.py           # Discord bot
```

## License

MIT License - See LICENSE file
