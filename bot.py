import asyncio
import signal
import sys
import logging
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse
import discord
from discord.ext import commands
from config import DISCORD_TOKEN, DISCORD_CHANNEL_ID, CHECK_INTERVAL, ALLOWED_DOMAINS
from database import Database
from scheduler import StockScheduler
from models import Product, TrackedProduct

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='/', intents=intents)
db = Database()
scheduler: Optional[StockScheduler] = None

def validate_url(url: str) -> tuple[bool, str]:
    """Validate URL format and domain"""
    try:
        parsed = urlparse(url)
        
        # Check if URL is valid
        if not parsed.scheme or not parsed.netloc:
            return False, "Invalid URL format. Must include http:// or https://"
        
        # Check if domain is allowed
        domain = parsed.netloc.lower()
        # Remove www. prefix if present
        if domain.startswith('www.'):
            domain = domain[4:]
        
        if domain not in ALLOWED_DOMAINS:
            allowed_list = ', '.join(ALLOWED_DOMAINS)
            return False, f"Domain not allowed. Allowed domains: {allowed_list}"
        
        return True, ""
    except Exception as e:
        return False, f"URL validation error: {str(e)}"

@bot.event
async def on_ready():
    """Called when bot is ready"""
    logger.info(f'{bot.user} has connected to Discord!')
    logger.info(f'Bot is in {len(bot.guilds)} guilds')
    
    # Start the stock monitoring scheduler
    global scheduler
    scheduler = StockScheduler(bot, db)
    await scheduler.start()
    
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
            name='for Pokémon & One Piece booster boxes'
        )
    )

@bot.tree.command(name='track', description='Add a product URL to monitor')
async def track(interaction: discord.Interaction, url: str, name: Optional[str] = None):
    """Add a product to track"""
    try:
        # Validate URL
        is_valid, error_message = validate_url(url)
        if not is_valid:
            await interaction.response.send_message(
                f"❌ {error_message}",
                ephemeral=True
            )
            return
        
        # Generate product ID
        product_id = f"user_{hash(url) % 10000000}"
        
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
            f"✅ Now tracking: {name or url}\n"
            f"You'll receive alerts when this comes back in stock!",
            ephemeral=True
        )
        logger.info(f"User {interaction.user.id} started tracking: {url}")
    
    except Exception as e:
        logger.error(f"Error in track command: {e}", exc_info=True)
        await interaction.response.send_message(
            f"❌ Error adding product: {str(e)}",
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
            title="📦 Tracked Booster Boxes",
            description=f"Currently monitoring {len(products)} booster boxes",
            color=discord.Color.blue()
        )
        
        # Group by retailer
        by_retailer = {}
        for product in products:
            if product.retailer not in by_retailer:
                by_retailer[product.retailer] = []
            by_retailer[product.retailer].append(product)
        
        for retailer, prods in by_retailer.items():
            in_stock = sum(1 for p in prods if p.in_stock)
            value = f"{len(prods)} boxes tracked\n{in_stock} currently in stock"
            embed.add_field(name=retailer, value=value, inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    except Exception as e:
        logger.error(f"Error in list command: {e}", exc_info=True)
        await interaction.response.send_message(
            f"❌ Error listing products: {str(e)}",
            ephemeral=True
        )

@bot.tree.command(name='remove', description='Remove a tracked product')
async def remove(interaction: discord.Interaction, product_id: str):
    """Remove a product from tracking"""
    try:
        db.remove_tracked_product(product_id)
        await interaction.response.send_message(
            f"✅ Removed product {product_id} from tracking",
            ephemeral=True
        )
        logger.info(f"User {interaction.user.id} removed tracking for: {product_id}")
    except Exception as e:
        logger.error(f"Error in remove command: {e}", exc_info=True)
        await interaction.response.send_message(
            f"❌ Error removing product: {str(e)}",
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
                "😔 No booster boxes currently in stock",
                ephemeral=True
            )
            return
        
        embed = discord.Embed(
            title="✅ In Stock Booster Boxes",
            description=f"Found {len(in_stock_products)} boxes in stock",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        
        for product in in_stock_products[:10]:  # Show max 10
            price_str = f"${product.price:.2f}" if product.price else "Price unknown"
            embed.add_field(
                name=f"{product.name[:50]}...",
                value=f"{product.retailer} | {price_str}\n[View Product]({product.url})",
                inline=False
            )
        
        if len(in_stock_products) > 10:
            embed.set_footer(text=f"And {len(in_stock_products) - 10} more...")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    except Exception as e:
        logger.error(f"Error in status command: {e}", exc_info=True)
        await interaction.response.send_message(
            f"❌ Error checking status: {str(e)}",
            ephemeral=True
        )

@bot.tree.command(name='alerts', description='Toggle stock alerts on/off')
async def toggle_alerts(interaction: discord.Interaction, enabled: bool):
    """Toggle alerts"""
    try:
        # Store preference in database (to be implemented)
        status = "enabled" if enabled else "disabled"
        await interaction.response.send_message(
            f"🔔 Stock alerts are now {status}",
            ephemeral=True
        )
        logger.info(f"User {interaction.user.id} {status} alerts")
    except Exception as e:
        logger.error(f"Error in alerts command: {e}", exc_info=True)
        await interaction.response.send_message(
            f"❌ Error toggling alerts: {str(e)}",
            ephemeral=True
        )

@bot.tree.command(name='force_check', description='Force an immediate stock check (Admin only)')
async def force_check(interaction: discord.Interaction):
    """Force an immediate stock check"""
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
                "❌ Scheduler not initialized yet. Please try again in a moment.",
                ephemeral=True
            )
    except Exception as e:
        logger.error(f"Error in force_check command: {e}", exc_info=True)
        await interaction.followup.send(
            f"❌ Error during stock check: {str(e)}",
            ephemeral=True
        )

@bot.tree.command(name='help_bot', description='Show help information')
async def help_command(interaction: discord.Interaction):
    """Show help"""
    embed = discord.Embed(
        title="📖 Stock Alert Bot Help",
        description="Monitor Pokémon & One Piece booster boxes across Melbourne retailers",
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
    
    for command, description in commands_info:
        embed.add_field(name=command, value=description, inline=False)
    
    embed.add_field(
        name="Monitored Retailers",
        value="EB Games, JB Hi-Fi, Target, Big W, Kmart",
        inline=False
    )
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

async def send_stock_alert(product: Product, channel_id: Optional[int] = None):
    """Send a stock alert to Discord"""
    if not channel_id:
        channel_id = DISCORD_CHANNEL_ID
    
    channel = bot.get_channel(channel_id)
    if not channel:
        logger.error(f"Could not find channel {channel_id}")
        return
    
    # Determine emoji based on category
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
    
    # Add @everyone mention for urgent alerts
    try:
        await channel.send("@everyone 🚨 STOCK ALERT!", embed=embed)
        logger.info(f"Stock alert sent for {product.name}")
    except Exception as e:
        logger.error(f"Failed to send stock alert: {e}")

async def shutdown(signal, loop):
    """Cleanup tasks tied to the service's shutdown."""
    logger.info(f"Received exit signal {signal.name}...")
    
    # Stop the scheduler
    if scheduler:
        logger.info("Stopping scheduler...")
        await scheduler.stop()
    
    # Close the bot
    logger.info("Closing Discord bot...")
    await bot.close()
    
    # Cancel all running tasks
    logger.info("Cancelling outstanding tasks...")
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    [task.cancel() for task in tasks]
    
    logger.info(f"Cancelled {len(tasks)} outstanding tasks")
    await asyncio.gather(*tasks, return_exceptions=True)
    loop.stop()

async def main():
    """Main entry point"""
    # Validate configuration
    if not DISCORD_TOKEN:
        logger.error("❌ DISCORD_TOKEN not set! Please create a .env file with your bot token.")
        return
    
    if not DISCORD_CHANNEL_ID:
        logger.error("❌ DISCORD_CHANNEL_ID not set! Please set it in your .env file.")
        return
    
    # Setup signal handlers for graceful shutdown
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

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down...")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
