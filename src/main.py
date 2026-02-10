"""Main Discord bot implementation."""
import asyncio
import logging
import signal
import sys
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse

import discord
from discord.ext import commands

from src.config import (
    DISCORD_TOKEN, DISCORD_CHANNEL_ID,
    LOG_LEVEL, LOG_FORMAT, LOG_FILE,
    ALLOWED_DOMAINS
)
from src.services.database import Database
from src.services.scheduler import StockScheduler
from src.models.product import StockAlert, TrackedProduct
from src.utils.health import HealthChecker
from src.utils.validation import validate_config
from src.utils.metrics import metrics

# Setup logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format=LOG_FORMAT,
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Discord setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='/', intents=intents)
db: Optional[Database] = None
scheduler: Optional[StockScheduler] = None
health_checker: Optional[HealthChecker] = None


def validate_url(url: str) -> tuple[bool, str]:
    """Validate URL format and domain."""
    try:
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return False, "Invalid URL format"
        
        domain = parsed.netloc.lower()
        if domain.startswith('www.'):
            domain = domain[4:]
        
        if domain not in ALLOWED_DOMAINS:
            return False, "Domain not in allowed list"
        
        return True, ""
    except Exception as e:
        return False, str(e)


async def send_stock_alert(alert: StockAlert, max_retries: int = 3) -> bool:
    """Send a stock alert to Discord with rate limit handling.
    
    Args:
        alert: The stock alert to send
        max_retries: Maximum number of retry attempts
        
    Returns:
        bool: True if alert was sent successfully, False otherwise
    """
    channel = bot.get_channel(DISCORD_CHANNEL_ID)
    if not channel:
        logger.error(f"Channel {DISCORD_CHANNEL_ID} not found")
        return False
    
    product = alert.product
    emoji = "🎴" if product.category == 'pokemon' else "🏴‍☠️"
    color = discord.Color.red() if product.category == 'pokemon' else discord.Color.blue()
    
    embed = discord.Embed(
        title=f"{emoji} IN STOCK: {product.name[:100]}",
        url=product.url,
        description=f"**{product.retailer}** just got stock!",
        color=color,
        timestamp=datetime.now()
    )
    
    if product.price:
        embed.add_field(name="💰 Price", value=f"${product.price:.2f} AUD", inline=True)
    if product.set_name:
        embed.add_field(name="📦 Set", value=product.set_name, inline=True)
    embed.add_field(name="🏪 Retailer", value=product.retailer, inline=True)
    if product.image_url:
        embed.set_thumbnail(url=product.image_url)
    embed.set_footer(text="Act fast! Stock may sell out quickly.")
    
    # Attempt to send with retry logic for rate limits
    for attempt in range(max_retries):
        try:
            await channel.send("@everyone 🚨 STOCK ALERT!", embed=embed)
            logger.info(f"Alert sent for {product.name}")
            return True
            
        except discord.HTTPException as e:
            if e.status == 429:  # Rate limited
                retry_after = getattr(e, 'retry_after', 5)
                logger.warning(f"Rate limited by Discord. Waiting {retry_after}s... (attempt {attempt + 1}/{max_retries})")
                await asyncio.sleep(retry_after)
                
            elif e.status >= 500:  # Server error
                logger.warning(f"Discord server error {e.status}. Retrying... (attempt {attempt + 1}/{max_retries})")
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
                
            else:
                logger.error(f"Discord HTTP error {e.status}: {e}")
                return False
                
        except discord.Forbidden:
            logger.error(f"Bot doesn't have permission to send messages in channel {DISCORD_CHANNEL_ID}")
            return False
            
        except Exception as e:
            logger.error(f"Failed to send alert: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)
            else:
                return False
    
    logger.error(f"Failed to send alert after {max_retries} attempts")
    return False


@bot.event
async def on_ready():
    """Called when bot is ready."""
    global db, scheduler, health_checker
    
    logger.info(f'{bot.user} has connected to Discord!')
    
    # Initialize database
    db = Database()
    await db.connect()
    
    # Start scheduler
    scheduler = StockScheduler(bot, db, send_stock_alert)
    await scheduler.start()
    
    # Initialize health checker
    health_checker = HealthChecker(bot, db, scheduler)
    
    # Sync commands
    try:
        synced = await bot.tree.sync()
        logger.info(f"Synced {len(synced)} command(s)")
    except Exception as e:
        logger.error(f"Failed to sync commands: {e}")
    
    # Set bot status
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name='for Pokemon & One Piece booster boxes'
        )
    )


@bot.tree.command(name='track', description='Add a product URL to monitor')
async def track(interaction: discord.Interaction, url: str, name: Optional[str] = None):
    """Add a product to track."""
    try:
        is_valid, error_msg = validate_url(url)
        if not is_valid:
            await interaction.response.send_message(f"❌ {error_msg}", ephemeral=True)
            return
        
        tracked = TrackedProduct(
            id=f"user_{hash(url) % 10000000}",
            url=url,
            name=name,
            added_by=interaction.user.id,
            alert_channel_id=interaction.channel_id
        )
        
        await db.add_tracked_product(tracked)
        
        await interaction.response.send_message(
            f"✅ Now tracking: {name or url}",
            ephemeral=True
        )
        logger.info(f"User {interaction.user.id} started tracking: {url}")
    
    except Exception as e:
        logger.error(f"Error in track command: {e}", exc_info=True)
        await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)


@bot.tree.command(name='list', description='Show all tracked products')
async def list_cmd(interaction: discord.Interaction):
    """List all tracked products."""
    try:
        products = await db.get_all_products()
        
        if not products:
            await interaction.response.send_message("No products are currently being tracked.", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="📦 Tracked Booster Boxes",
            description=f"Monitoring {len(products)} booster boxes",
            color=discord.Color.blue()
        )
        
        by_retailer = {}
        for p in products:
            by_retailer.setdefault(p.retailer, []).append(p)
        
        for retailer, prods in by_retailer.items():
            in_stock = sum(1 for p in prods if p.in_stock)
            embed.add_field(
                name=retailer,
                value=f"{len(prods)} tracked | {in_stock} in stock",
                inline=True
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    except Exception as e:
        logger.error(f"Error in list command: {e}", exc_info=True)
        await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)


@bot.tree.command(name='status', description='Check current stock status')
async def status(interaction: discord.Interaction, retailer: Optional[str] = None):
    """Check current stock status."""
    try:
        if retailer:
            products = await db.get_products_by_retailer(retailer)
        else:
            products = await db.get_in_stock_products()
        
        in_stock = [p for p in products if p.in_stock] if retailer else products
        
        if not in_stock:
            await interaction.response.send_message("😔 No booster boxes currently in stock", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="✅ In Stock Booster Boxes",
            description=f"Found {len(in_stock)} boxes in stock",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        
        for product in in_stock[:10]:
            price_str = f"${product.price:.2f}" if product.price else "Price unknown"
            embed.add_field(
                name=f"{product.name[:50]}...",
                value=f"{product.retailer} | {price_str}\n[View Product]({product.url})",
                inline=False
            )
        
        if len(in_stock) > 10:
            embed.set_footer(text=f"And {len(in_stock) - 10} more...")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    except Exception as e:
        logger.error(f"Error in status command: {e}", exc_info=True)
        await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)


@bot.tree.command(name='force_check', description='Force an immediate stock check')
async def force_check(interaction: discord.Interaction):
    """Force an immediate stock check."""
    try:
        await interaction.response.send_message(
            "🔄 Starting forced stock check... This may take a few minutes.",
            ephemeral=True
        )
        
        if scheduler:
            products = await scheduler.force_check()
            await interaction.followup.send(
                f"✅ Check complete! Found {len(products)} booster boxes.",
                ephemeral=True
            )
        else:
            await interaction.followup.send(
                "❌ Scheduler not initialized yet. Please try again.",
                ephemeral=True
            )
    except Exception as e:
        logger.error(f"Error in force_check command: {e}", exc_info=True)
        await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)


@bot.tree.command(name='stats', description='Show bot statistics')
async def stats_cmd(interaction: discord.Interaction):
    """Show bot statistics."""
    try:
        db_stats = await db.get_stats()
        scheduler_status = scheduler.get_status() if scheduler else {'running': False}
        
        embed = discord.Embed(
            title="📊 Bot Statistics",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        
        embed.add_field(name="Total Products", value=db_stats['total_products'], inline=True)
        embed.add_field(name="In Stock", value=db_stats['in_stock'], inline=True)
        embed.add_field(name="Alerts (24h)", value=db_stats['alerts_24h'], inline=True)
        
        status_emoji = "🟢" if scheduler_status['running'] else "🔴"
        embed.add_field(
            name="Scheduler",
            value=f"{status_emoji} {'Running' if scheduler_status['running'] else 'Stopped'}",
            inline=True
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    except Exception as e:
        logger.error(f"Error in stats command: {e}", exc_info=True)
        await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)


@bot.tree.command(name='health', description='Check bot health status')
async def health_cmd(interaction: discord.Interaction):
    """Check bot health status."""
    try:
        if not health_checker:
            await interaction.response.send_message(
                "❌ Health checker not initialized yet. Please try again in a moment.",
                ephemeral=True
            )
            return
        
        # Run health checks
        health_status = await health_checker.check_all()
        
        # Create embed
        status_emoji = "🟢" if health_status['healthy'] else "🔴"
        embed = discord.Embed(
            title=f"{status_emoji} Bot Health Status",
            description=f"Overall: {'Healthy' if health_status['healthy'] else 'Unhealthy'}",
            color=discord.Color.green() if health_status['healthy'] else discord.Color.red(),
            timestamp=datetime.now()
        )
        
        # Add each component status
        for check in health_status['checks']:
            component_emoji = "✅" if check['healthy'] else "❌"
            value = f"{component_emoji} {check['message']}"
            if check.get('details'):
                details_str = '\n'.join([f"  • {k}: {v}" for k, v in check['details'].items()])
                value += f"\n```{details_str}```"
            
            embed.add_field(
                name=check['component'].title(),
                value=value,
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    except Exception as e:
        logger.error(f"Error in health command: {e}", exc_info=True)
        await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)


@bot.tree.command(name='metrics', description='Show bot metrics (Prometheus format)')
async def metrics_cmd(interaction: discord.Interaction):
    """Show Prometheus metrics."""
    try:
        # Get metrics in Prometheus format
        prometheus_output = metrics.to_prometheus()

        # Create embed with summary
        stats = metrics.get_stats()

        embed = discord.Embed(
            title="📊 Bot Metrics",
            description="Prometheus-compatible metrics",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )

        # Add counter summary
        counters = stats['counters']
        embed.add_field(
            name="📈 Counters",
            value=f"Alerts Sent: {counters.get('alerts_sent_total', 0)}\n"
                  f"Stock Checks: {counters.get('stock_checks_total', 0)}\n"
                  f"Products Found: {counters.get('products_discovered_total', 0)}",
            inline=True
        )

        # Add gauge summary
        gauges = stats['gauges']
        embed.add_field(
            name="📊 Gauges",
            value=f"Products Tracked: {gauges.get('products_tracked', 0):.0f}\n"
                  f"In Stock: {gauges.get('products_in_stock', 0):.0f}\n"
                  f"Scheduler: {'Running' if gauges.get('scheduler_running', 0) == 1 else 'Stopped'}",
            inline=True
        )

        # Add histogram summary
        histograms = stats['histograms']
        alert_hist = histograms.get('alert_send_duration_seconds', {})
        embed.add_field(
            name="⏱️ Alert Latency",
            value=f"Count: {alert_hist.get('count', 0)}\n"
                  f"Total: {alert_hist.get('sum', 0):.3f}s",
            inline=True
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    except Exception as e:
        logger.error(f"Error in metrics command: {e}", exc_info=True)
        await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)


async def shutdown(signal_obj, loop):
    """Cleanup tasks for graceful shutdown."""
    logger.info(f"Received exit signal {signal_obj.name}...")
    
    if scheduler:
        await scheduler.stop()
    
    if db:
        await db.close()
    
    await bot.close()
    
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    [task.cancel() for task in tasks]
    await asyncio.gather(*tasks, return_exceptions=True)
    loop.stop()


async def main():
    """Main entry point."""
    # Validate configuration before starting
    try:
        validate_config()
    except Exception as e:
        logger.error(f"Configuration validation failed: {e}")
        return
    
    if not DISCORD_TOKEN:
        logger.error("DISCORD_TOKEN not set! Please check your .env file.")
        return
    
    if not DISCORD_CHANNEL_ID:
        logger.error("DISCORD_CHANNEL_ID not set! Please check your .env file.")
        return
    
    # Setup signal handlers
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda s=sig: asyncio.create_task(shutdown(s, loop)))
    
    try:
        logger.info("Starting bot...")
        await bot.start(DISCORD_TOKEN)
    except Exception as e:
        logger.error(f"Error starting bot: {e}", exc_info=True)
    finally:
        logger.info("Bot shutdown complete")
