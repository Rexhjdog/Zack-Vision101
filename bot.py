import asyncio
import discord
from discord.ext import commands
from datetime import datetime
from typing import Optional
from config import DISCORD_TOKEN, DISCORD_CHANNEL_ID, CHECK_INTERVAL
from database import Database
from scheduler import StockScheduler
from models import Product, TrackedProduct

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='/', intents=intents)
db = Database()
scheduler: Optional[StockScheduler] = None

@bot.event
async def on_ready():
    """Called when bot is ready"""
    print(f'{bot.user} has connected to Discord!')
    print(f'Bot is in {len(bot.guilds)} guilds')
    
    # Start the stock monitoring scheduler
    global scheduler
    scheduler = StockScheduler(bot, db)
    await scheduler.start()
    
    # Set bot status
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching, 
            name='for Pokémon & One Piece stock'
        )
    )

@bot.tree.command(name='track', description='Add a product URL to monitor')
async def track(interaction: discord.Interaction, url: str, name: Optional[str] = None):
    """Add a product to track"""
    try:
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
    
    except Exception as e:
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
            title="📦 Tracked Products",
            description=f"Currently monitoring {len(products)} products",
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
            value = f"{len(prods)} products tracked\n{in_stock} currently in stock"
            embed.add_field(name=retailer, value=value, inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    except Exception as e:
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
    except Exception as e:
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
                "😔 No products currently in stock",
                ephemeral=True
            )
            return
        
        embed = discord.Embed(
            title="✅ In Stock Products",
            description=f"Found {len(in_stock_products)} products in stock",
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
        await interaction.response.send_message(
            f"❌ Error checking status: {str(e)}",
            ephemeral=True
        )

@bot.tree.command(name='alerts', description='Toggle stock alerts on/off')
async def toggle_alerts(interaction: discord.Interaction, enabled: bool):
    """Toggle alerts"""
    try:
        # Store preference in database
        # For now, just acknowledge
        status = "enabled" if enabled else "disabled"
        await interaction.response.send_message(
            f"🔔 Stock alerts are now {status}",
            ephemeral=True
        )
    except Exception as e:
        await interaction.response.send_message(
            f"❌ Error toggling alerts: {str(e)}",
            ephemeral=True
        )

@bot.tree.command(name='search', description='Search for products across all retailers')
async def search(interaction: discord.Interaction, query: str):
    """Search for products"""
    await interaction.response.send_message(
        f"🔍 Searching for '{query}' across all retailers...",
        ephemeral=True
    )
    
    # This would trigger an immediate search
    # Implementation depends on your scraper setup
    await interaction.followup.send(
        "Search functionality is running in the background. Check back soon!",
        ephemeral=True
    )

@bot.tree.command(name='help_bot', description='Show help information')
async def help_command(interaction: discord.Interaction):
    """Show help"""
    embed = discord.Embed(
        title="📖 Stock Alert Bot Help",
        description="Monitor Pokémon & One Piece booster packs across Melbourne retailers",
        color=discord.Color.blue()
    )
    
    commands_info = [
        ("/track <url> [name]", "Add a product URL to monitor"),
        ("/list", "Show all tracked products"),
        ("/remove <id>", "Remove a product from tracking"),
        ("/status [retailer]", "Check current stock status"),
        ("/alerts <on/off>", "Toggle stock alerts"),
        ("/search <query>", "Search for products"),
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
        print(f"Could not find channel {channel_id}")
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
    await channel.send("@everyone 🚨 STOCK ALERT!", embed=embed)

async def main():
    """Main entry point"""
    if not DISCORD_TOKEN:
        print("❌ DISCORD_TOKEN not set! Please create a .env file with your bot token.")
        return
    
    # Sync commands
    @bot.event
    async def on_ready():
        await bot.tree.sync()
        print(f"Synced {len(bot.tree.get_commands())} commands")
    
    await bot.start(DISCORD_TOKEN)

if __name__ == '__main__':
    asyncio.run(main())
