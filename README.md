# Pokemon/One Piece TCG Stock Alert Bot

A Discord bot that monitors Melbourne-area retailers for Pokemon and One Piece booster pack stock availability.

## Features

- **Real-time Monitoring**: Checks 6 major Melbourne retailers every 2 minutes
- **Smart Alerts**: Only notifies when items come BACK in stock (no spam)
- **Multiple Retailers**: EB Games, JB Hi-Fi, Target, Big W, Kmart
- **Discord Integration**: Slash commands for easy management
- **Stock History**: Tracks price changes and availability over time
- **Booster Pack Focus**: Monitors only packs (no booster boxes)

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
5. Under "OAuth2" → "URL Generator":
   - Select `bot` scope
   - Select permissions: `Send Messages`, `Embed Links`, `Mention Everyone`, `Use Slash Commands`
   - Copy the generated URL and open it to invite the bot to your server

### 3. Get Channel ID

1. In Discord, enable Developer Mode (User Settings → Advanced)
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
| `/alerts <on/off>` | Toggle stock alerts |
| `/search <query>` | Search for products |
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
# Check interval (seconds)
CHECK_INTERVAL = 120  # 2 minutes

# Booster pack keywords
BOOSTER_KEYWORDS = ['booster pack', 'pack', 'blister', '3-pack', '6-pack']

# High rarity keywords
HIGH_RARITY_KEYWORDS = ['secret rare', 'alternate art', 'full art']

# Pokemon sets to track
POKEMON_SETS = ['Paldean Fates', 'Temporal Forces', '151', ...]

# One Piece sets to track
ONE_PIECE_SETS = ['Romance Dawn', 'Paramount War', ...]
```

## Project Structure

```
Zack-Vision101/
├── bot.py              # Discord bot with slash commands
├── scheduler.py        # Stock monitoring scheduler
├── database.py         # SQLite database operations
├── config.py           # Configuration settings
├── models.py           # Data models
├── scrapers/           # Retailer-specific scrapers
│   ├── base.py        # Base scraper class
│   ├── eb_games.py    # EB Games scraper
│   ├── jb_hifi.py     # JB Hi-Fi scraper
│   ├── target_au.py   # Target Australia scraper
│   ├── big_w.py       # Big W scraper
│   └── kmart.py       # Kmart scraper
├── requirements.txt    # Python dependencies
├── setup.py           # Setup script
├── .env.example       # Environment file template
├── .gitignore         # Git ignore rules
├── README.md          # This file
└── LICENSE            # MIT License
```

## How It Works

1. **Scheduler** runs every 2 minutes and checks all enabled retailers
2. **Scrapers** search for Pokemon and One Piece products on each retailer's website
3. **Database** tracks stock history to detect changes
4. **Alerts** are sent when:
   - An item comes back in stock
   - Price changes significantly
5. **Discord bot** provides commands to interact with the system

## Database

The bot uses SQLite to store:
- Products (name, URL, price, stock status)
- Stock history (timestamps of stock changes)
- Alerts (notification history)
- User-tracked products (custom URLs to monitor)

## Troubleshooting

### Bot won't start
- Check that `.env` file exists and has valid token
- Ensure Python 3.8+ is installed
- Run `pip install -r requirements.txt` again

### No alerts received
- Verify bot has correct channel permissions
- Check that the bot is in your Discord server
- Look at console output for errors

### Scraper errors
- Some sites may block bots
- Check your internet connection
- Retailers may change their website layout (scrapers may need updating)

## Contributing

Feel free to:
- Add more retailers
- Improve scrapers
- Add new features
- Report bugs

## License

MIT License - See LICENSE file

## Disclaimer

This bot is for educational purposes. Always respect retailers' Terms of Service and robots.txt files. Use responsibly and don't overload websites with requests.

## Support

If you have issues:
1. Check the logs in the console
2. Verify your Discord bot token and permissions
3. Make sure the channel ID is correct
4. Check that all dependencies are installed

Happy hunting for those rare cards! 🎴🏴‍☠️
