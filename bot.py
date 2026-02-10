import asyncio
import hashlib
import sys
import logging
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse
import discord
from discord import app_commands
from discord.ext import commands
from config import (
    DISCORD_TOKEN, DISCORD_CHANNEL_ID, ALLOWED_DOMAINS,
    MAX_EMBED_FIELDS, LOG_FILE,
)
from database import Database
from scheduler import StockScheduler
from models import Product, TrackedProduct

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout),
    ]
)
logger = logging.getLogger(__name__)

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='/', intents=intents)
db = Database()
scheduler: Optional[StockScheduler] = None


def _generate_tracked_product_id(url: str) -> str:
    """Generate a deterministic product ID from a URL.

    Uses hashlib.md5 instead of hash() because Python's hash() is
    randomized across sessions (PYTHONHASHSEED), making IDs non-deterministic.
    """
    return f"user_{hashlib.md5(url.encode()).hexdigest()[:12]}"


def validate_url(url: str) -> tuple[bool, str]:
    """Validate URL format and domain against allowlist"""
    try:
        parsed = urlparse(url)

        if not parsed.scheme or not parsed.netloc:
            return False, "Invalid URL format. Must include http:// or https://"

        if parsed.scheme not in ('http', 'https'):
            return False, "Only http and https URLs are allowed"

        domain = parsed.netloc.lower()
        if domain.startswith('www.'):
            domain = domain[4:]

        if domain not in ALLOWED_DOMAINS:
            allowed_list = ', '.join(ALLOWED_DOMAINS)
            return False, f"Domain not allowed. Allowed domains: {allowed_list}"

        return True, ""
    except Exception as e:
        return False, f"URL validation error: {str(e)}"


# ──────────────────────────────────────────
# Alert sending (passed as callback to scheduler)
# ──────────────────────────────────────────

async def send_stock_alert(product: Product, channel_id: Optional[int] = None):
    """Send a stock alert to the configured Discord channel"""
    if not channel_id:
        channel_id = DISCORD_CHANNEL_ID

    channel = bot.get_channel(channel_id)
    if not channel:
        logger.error(f"Could not find channel {channel_id}")
        return

    emoji = "\U0001f3b4" if product.category == 'pokemon' else "\U0001f3f4\u200d\u2620\ufe0f"
    color = discord.Color.red() if product.category == 'pokemon' else discord.Color.blue()

    embed = discord.Embed(
        title=f"{emoji} IN STOCK: {product.name[:100]}",
        url=product.url,
        description=f"**{product.retailer}** just got stock!",
        color=color,
        timestamp=datetime.now()
    )

    if product.price:
        embed.add_field(name="Price", value=f"${product.price:.2f} AUD", inline=True)

    if product.set_name:
        embed.add_field(name="Set", value=product.set_name, inline=True)

    embed.add_field(name="Retailer", value=product.retailer, inline=True)

    if product.image_url:
        embed.set_thumbnail(url=product.image_url)

    embed.set_footer(text="Act fast! Stock may sell out quickly.")

    try:
        await channel.send("@everyone STOCK ALERT!", embed=embed)
        logger.info(f"Stock alert sent for {product.name}")
    except Exception as e:
        logger.error(f"Failed to send stock alert: {e}")


# ──────────────────────────────────────────
# Bot events
# ──────────────────────────────────────────

@bot.event
async def on_ready():
    """Called when bot is ready"""
    logger.info(f'{bot.user} has connected to Discord!')
    logger.info(f'Bot is in {len(bot.guilds)} guilds')

    # Sync commands first
    try:
        synced = await bot.tree.sync()
        logger.info(f"Synced {len(synced)} command(s)")
    except Exception as e:
        logger.error(f"Failed to sync commands: {e}")

    # Start the stock monitoring scheduler (with callback, no circular import)
    global scheduler
    scheduler = StockScheduler(db=db, alert_callback=send_stock_alert)
    await scheduler.start()

    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name='for TCG booster boxes'
        )
    )


# ──────────────────────────────────────────
# Slash commands
# ──────────────────────────────────────────

@bot.tree.command(name='track', description='Add a product URL to monitor')
async def track(interaction: discord.Interaction, url: str, name: Optional[str] = None):
    """Add a product to track"""
    try:
        is_valid, error_message = validate_url(url)
        if not is_valid:
            await interaction.response.send_message(f"Error: {error_message}", ephemeral=True)
            return

        product_id = _generate_tracked_product_id(url)

        tracked = TrackedProduct(
            id=product_id,
            url=url,
            name=name,
            added_by=interaction.user.id,
            added_at=datetime.now(),
            enabled=True,
            alert_channel_id=interaction.channel_id
        )

        db.add_tracked_product(tracked)

        await interaction.response.send_message(
            f"Now tracking: {name or url}\n"
            f"You'll receive alerts when this comes back in stock!",
            ephemeral=True
        )
        logger.info(f"User {interaction.user.id} started tracking: {url}")

    except Exception as e:
        logger.error(f"Error in track command: {e}", exc_info=True)
        await interaction.response.send_message(
            f"Error adding product: {str(e)}",
            ephemeral=True
        )


@bot.tree.command(name='list', description='Show all tracked products')
async def list_tracked(interaction: discord.Interaction):
    """List all tracked products"""
    try:
        tracked = db.get_tracked_products()
        products = db.get_all_products()

        if not tracked and not products:
            await interaction.response.send_message(
                "No products are currently being tracked.",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title="Tracked Booster Boxes",
            description=f"Currently monitoring {len(products)} booster boxes",
            color=discord.Color.blue()
        )

        by_retailer = {}
        for product in products:
            by_retailer.setdefault(product.retailer, []).append(product)

        for retailer, prods in by_retailer.items():
            in_stock = sum(1 for p in prods if p.in_stock)
            value = f"{len(prods)} boxes tracked\n{in_stock} currently in stock"
            embed.add_field(name=retailer, value=value, inline=True)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    except Exception as e:
        logger.error(f"Error in list command: {e}", exc_info=True)
        await interaction.response.send_message(
            f"Error listing products: {str(e)}",
            ephemeral=True
        )


@bot.tree.command(name='remove', description='Remove a tracked product')
async def remove(interaction: discord.Interaction, product_id: str):
    """Remove a product from tracking"""
    try:
        db.remove_tracked_product(product_id)
        await interaction.response.send_message(
            f"Removed product {product_id} from tracking",
            ephemeral=True
        )
        logger.info(f"User {interaction.user.id} removed tracking for: {product_id}")
    except Exception as e:
        logger.error(f"Error in remove command: {e}", exc_info=True)
        await interaction.response.send_message(
            f"Error removing product: {str(e)}",
            ephemeral=True
        )


@bot.tree.command(name='status', description='Check current stock status')
async def status(interaction: discord.Interaction, retailer: Optional[str] = None):
    """Check current stock status"""
    try:
        if retailer:
            products = db.get_products_by_retailer(retailer)
        else:
            products = db.get_all_products()

        in_stock_products = [p for p in products if p.in_stock]

        if not in_stock_products:
            await interaction.response.send_message(
                "No booster boxes currently in stock.",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title="In Stock Booster Boxes",
            description=f"Found {len(in_stock_products)} boxes in stock",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )

        for product in in_stock_products[:MAX_EMBED_FIELDS]:
            price_str = f"${product.price:.2f}" if product.price else "Price unknown"
            embed.add_field(
                name=f"{product.name[:50]}...",
                value=f"{product.retailer} | {price_str}\n[View Product]({product.url})",
                inline=False
            )

        if len(in_stock_products) > MAX_EMBED_FIELDS:
            embed.set_footer(text=f"And {len(in_stock_products) - MAX_EMBED_FIELDS} more...")

        await interaction.response.send_message(embed=embed, ephemeral=True)

    except Exception as e:
        logger.error(f"Error in status command: {e}", exc_info=True)
        await interaction.response.send_message(
            f"Error checking status: {str(e)}",
            ephemeral=True
        )


@bot.tree.command(name='alerts', description='Toggle stock alerts on/off')
async def toggle_alerts(interaction: discord.Interaction, enabled: bool):
    """Toggle alerts for the current user (persisted to database)"""
    try:
        db.set_user_preference(interaction.user.id, enabled)
        status_text = "enabled" if enabled else "disabled"
        await interaction.response.send_message(
            f"Stock alerts are now {status_text}.",
            ephemeral=True
        )
        logger.info(f"User {interaction.user.id} {status_text} alerts")
    except Exception as e:
        logger.error(f"Error in alerts command: {e}", exc_info=True)
        await interaction.response.send_message(
            f"Error toggling alerts: {str(e)}",
            ephemeral=True
        )


@bot.tree.command(name='force_check', description='Force an immediate stock check (Admin only)')
@app_commands.checks.has_permissions(administrator=True)
async def force_check(interaction: discord.Interaction):
    """Force an immediate stock check (requires Administrator permission)"""
    try:
        await interaction.response.send_message(
            "Starting forced stock check...",
            ephemeral=True
        )

        if scheduler:
            products = await scheduler.force_check()
            await interaction.followup.send(
                f"Check complete! Found {len(products)} booster boxes.",
                ephemeral=True
            )
        else:
            await interaction.followup.send(
                "Scheduler not initialized yet. Please try again in a moment.",
                ephemeral=True
            )
    except Exception as e:
        logger.error(f"Error in force_check command: {e}", exc_info=True)
        await interaction.followup.send(
            f"Error during stock check: {str(e)}",
            ephemeral=True
        )


@force_check.error
async def force_check_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    """Handle permission errors for force_check"""
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message(
            "You need Administrator permission to use this command.",
            ephemeral=True
        )


@bot.tree.command(name='help_bot', description='Show help information')
async def help_command(interaction: discord.Interaction):
    """Show help"""
    embed = discord.Embed(
        title="Stock Alert Bot Help",
        description="Monitor Pokemon & One Piece booster boxes across Melbourne retailers",
        color=discord.Color.blue()
    )

    commands_info = [
        ("/track <url> [name]", "Add a product URL to monitor"),
        ("/list", "Show all tracked products"),
        ("/remove <id>", "Remove a product from tracking"),
        ("/status [retailer]", "Check current stock status"),
        ("/alerts <on/off>", "Toggle stock alerts"),
        ("/force_check", "Force immediate stock check (Admin)"),
    ]

    for cmd, description in commands_info:
        embed.add_field(name=cmd, value=description, inline=False)

    embed.add_field(
        name="Monitored Retailers",
        value="EB Games, JB Hi-Fi, Target, Big W, Kmart",
        inline=False
    )

    await interaction.response.send_message(embed=embed, ephemeral=True)


# ──────────────────────────────────────────
# Shutdown & main
# ──────────────────────────────────────────

async def shutdown():
    """Cleanup tasks tied to the service's shutdown."""
    logger.info("Shutting down...")

    if scheduler:
        logger.info("Stopping scheduler...")
        await scheduler.stop()

    logger.info("Closing Discord bot...")
    await bot.close()

    logger.info("Cancelling outstanding tasks...")
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    for task in tasks:
        task.cancel()

    logger.info(f"Cancelled {len(tasks)} outstanding tasks")
    await asyncio.gather(*tasks, return_exceptions=True)


async def main():
    """Main entry point"""
    if not DISCORD_TOKEN:
        logger.error("DISCORD_TOKEN not set! Please create a .env file with your bot token.")
        return

    if not DISCORD_CHANNEL_ID:
        logger.error("DISCORD_CHANNEL_ID not set! Please set it in your .env file.")
        return

    try:
        logger.info("Starting bot...")
        await bot.start(DISCORD_TOKEN)
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error(f"Error starting bot: {e}", exc_info=True)
    finally:
        await shutdown()
        logger.info("Bot shutdown complete")


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down...")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
