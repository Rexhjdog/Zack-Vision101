"""Discord bot – slash commands and stock-alert delivery."""

from __future__ import annotations

import asyncio
import logging
import signal
from itertools import groupby

import discord
from discord import app_commands
from discord.ext import commands

from src.config import ALLOWED_DOMAINS, DISCORD_CHANNEL_ID, DISCORD_TOKEN, RETAILERS
from src.models.product import AlertType, StockAlert, TrackedProduct
from src.services.database import Database
from src.services.scheduler import StockScheduler
from src.utils.logging_config import setup_logging

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Bot setup
# ------------------------------------------------------------------

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="/", intents=intents)

db = Database()
scheduler: StockScheduler | None = None


# ------------------------------------------------------------------
# Alert delivery
# ------------------------------------------------------------------

async def send_stock_alert(alert: StockAlert) -> None:
    """Send a Discord embed for a stock alert."""
    channel = bot.get_channel(DISCORD_CHANNEL_ID)
    if channel is None:
        logger.error("Alert channel %d not found", DISCORD_CHANNEL_ID)
        return

    product = alert.product
    emoji = "\U0001f3b4" if product.category == "pokemon" else "\U0001f3f4\u200d\u2620\ufe0f"

    if alert.alert_type == AlertType.IN_STOCK:
        title = f"{emoji} IN STOCK: {product.name[:100]}"
        colour = discord.Color.green()
        desc = f"**{product.retailer}** just got stock!"
    elif alert.alert_type == AlertType.OUT_OF_STOCK:
        title = f"\u274c OUT OF STOCK: {product.name[:100]}"
        colour = discord.Color.red()
        desc = f"**{product.retailer}** is now out of stock."
    elif alert.alert_type == AlertType.PRICE_CHANGE:
        title = f"\U0001f4b0 PRICE CHANGE: {product.name[:100]}"
        colour = discord.Color.gold()
        old = f"${alert.previous_price:.2f}" if alert.previous_price else "N/A"
        new = product.display_price
        desc = f"**{product.retailer}** price: {old} \u2192 {new}"
    elif alert.alert_type == AlertType.NEW_PRODUCT:
        title = f"\U0001f195 NEW: {product.name[:100]}"
        colour = discord.Color.blue()
        desc = f"New listing found at **{product.retailer}**!"
    else:
        return

    embed = discord.Embed(title=title, url=product.url, description=desc, color=colour)
    embed.add_field(name="Price", value=product.display_price, inline=True)
    embed.add_field(name="Retailer", value=product.retailer, inline=True)
    if product.set_name:
        embed.add_field(name="Set", value=product.set_name, inline=True)
    if product.image_url:
        embed.set_thumbnail(url=product.image_url)

    for attempt in range(1, 4):
        try:
            mention = "@everyone " if alert.is_restock else ""
            await channel.send(content=mention, embed=embed)  # type: ignore[union-attr]
            return
        except discord.HTTPException as exc:
            if exc.status == 429:
                retry_after = getattr(exc, "retry_after", 2 * attempt)
                logger.warning("Rate limited, retrying in %.1fs", retry_after)
                await asyncio.sleep(retry_after)
            else:
                logger.error("Failed to send alert: %s", exc)
                return


# ------------------------------------------------------------------
# Slash commands
# ------------------------------------------------------------------

@bot.tree.command(name="track", description="Track a product URL for stock alerts")
@app_commands.describe(url="Product URL to monitor", name="Optional friendly name")
async def cmd_track(interaction: discord.Interaction, url: str, name: str = "") -> None:
    # Basic domain validation
    from urllib.parse import urlparse

    parsed = urlparse(url)
    if parsed.hostname not in ALLOWED_DOMAINS:
        await interaction.response.send_message(
            f"URL must be from a supported retailer: {', '.join(sorted(ALLOWED_DOMAINS))}",
            ephemeral=True,
        )
        return

    retailer = ""
    for cfg in RETAILERS.values():
        if parsed.hostname and parsed.hostname in cfg["base_url"]:
            retailer = cfg["name"]
            break

    tp = TrackedProduct(
        url=url,
        name=name or url,
        added_by=interaction.user.id,
        retailer=retailer,
    )
    await db.add_tracked(tp)
    await interaction.response.send_message(
        f"Now tracking: **{tp.name}** ({retailer or 'unknown retailer'})"
    )


@bot.tree.command(name="untrack", description="Stop tracking a product URL")
@app_commands.describe(url="Product URL to stop monitoring")
async def cmd_untrack(interaction: discord.Interaction, url: str) -> None:
    removed = await db.remove_tracked(url)
    if removed:
        await interaction.response.send_message(f"Removed tracking for: {url}")
    else:
        await interaction.response.send_message("That URL wasn't being tracked.", ephemeral=True)


@bot.tree.command(name="list", description="Show all tracked products")
async def cmd_list(interaction: discord.Interaction) -> None:
    tracked = await db.get_all_tracked()
    if not tracked:
        await interaction.response.send_message("No products are being tracked.")
        return

    embed = discord.Embed(title="Tracked Products", color=discord.Color.blue())
    grouped = groupby(sorted(tracked, key=lambda t: t.retailer), key=lambda t: t.retailer)
    for retailer, items in grouped:
        lines = [f"[{t.name}]({t.url})" for t in items]
        embed.add_field(
            name=retailer or "Unknown",
            value="\n".join(lines[:10]) or "None",
            inline=False,
        )
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="status", description="Check current stock status")
@app_commands.describe(retailer="Optional retailer filter")
async def cmd_status(interaction: discord.Interaction, retailer: str = "") -> None:
    if retailer:
        products = await db.get_products_by_retailer(retailer)
    else:
        products = await db.get_all_products()

    in_stock = [p for p in products if p.in_stock]
    if not in_stock:
        await interaction.response.send_message("No products currently in stock.")
        return

    embed = discord.Embed(
        title=f"In Stock ({len(in_stock)} items)",
        color=discord.Color.green(),
    )
    for p in in_stock[:25]:
        embed.add_field(
            name=p.name[:60],
            value=f"{p.retailer} | {p.display_price} | [Link]({p.url})",
            inline=False,
        )
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="force_check", description="Trigger an immediate stock check")
async def cmd_force_check(interaction: discord.Interaction) -> None:
    if scheduler is None or not scheduler.is_running:
        await interaction.response.send_message(
            "Scheduler is not running.", ephemeral=True
        )
        return

    await interaction.response.defer()
    alerts = await scheduler.run_once()
    await interaction.followup.send(
        f"Check complete. Found **{len(alerts)}** new alert(s)."
    )


@bot.tree.command(name="stats", description="Show bot statistics")
async def cmd_stats(interaction: discord.Interaction) -> None:
    total = await db.get_total_product_count()
    in_stock = await db.get_in_stock_count()
    recent_alerts = await db.get_recent_alert_count(24)

    s = scheduler.stats if scheduler else None
    embed = discord.Embed(title="Bot Statistics", color=discord.Color.purple())
    embed.add_field(name="Total Products", value=str(total), inline=True)
    embed.add_field(name="In Stock", value=str(in_stock), inline=True)
    embed.add_field(name="Alerts (24h)", value=str(recent_alerts), inline=True)
    if s:
        embed.add_field(name="Total Checks", value=str(s.total_checks), inline=True)
        embed.add_field(name="Success", value=str(s.successful_checks), inline=True)
        embed.add_field(name="Failed", value=str(s.failed_checks), inline=True)
        embed.add_field(
            name="Scheduler",
            value="Running" if scheduler and scheduler.is_running else "Stopped",
            inline=True,
        )
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="health", description="Check bot health")
async def cmd_health(interaction: discord.Interaction) -> None:
    checks: dict[str, str] = {}

    # Discord
    checks["Discord"] = "OK" if bot.is_ready() else "NOT READY"

    # Database
    try:
        await db.get_total_product_count()
        checks["Database"] = "OK"
    except Exception as exc:
        checks["Database"] = f"ERROR: {exc}"

    # Scheduler
    checks["Scheduler"] = (
        "Running" if scheduler and scheduler.is_running else "Stopped"
    )

    embed = discord.Embed(title="Health Check", color=discord.Color.green())
    for name, status in checks.items():
        embed.add_field(name=name, value=status, inline=True)
    await interaction.response.send_message(embed=embed)


# ------------------------------------------------------------------
# Bot events
# ------------------------------------------------------------------

@bot.event
async def on_ready() -> None:
    global scheduler
    logger.info("Logged in as %s (id=%s)", bot.user, bot.user.id if bot.user else "?")
    try:
        synced = await bot.tree.sync()
        logger.info("Synced %d slash commands", len(synced))
    except Exception as exc:
        logger.error("Failed to sync commands: %s", exc)

    await db.connect()

    scheduler = StockScheduler(db, on_alert=send_stock_alert)
    scheduler.start()
    logger.info("Bot is ready and monitoring stock")


# ------------------------------------------------------------------
# Entrypoint
# ------------------------------------------------------------------

async def main() -> None:
    """Start the bot with graceful shutdown handling."""
    setup_logging()

    if not DISCORD_TOKEN:
        logger.critical("DISCORD_TOKEN not set")
        return

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(_shutdown()))

    try:
        async with bot:
            await bot.start(DISCORD_TOKEN)
    finally:
        if scheduler:
            await scheduler.stop()
        await db.close()


async def _shutdown() -> None:
    logger.info("Shutdown signal received")
    if scheduler:
        await scheduler.stop()
    await db.close()
    await bot.close()
