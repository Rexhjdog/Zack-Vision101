"""Stock monitoring scheduler."""
import asyncio
import logging
from datetime import datetime
from typing import List, Optional, Callable, Dict, Any
from dataclasses import dataclass, field

import discord

from src.config import CHECK_INTERVAL, RETAILERS, ALERT_COOLDOWN
from src.services.database import Database
from src.models.product import Product, StockAlert, AlertType
from src.scrapers import (
    EBGamesScraper,
    JBHiFiScraper,
    TargetScraper,
    BigWScraper,
    KmartScraper
)
from src.utils.metrics import metrics

logger = logging.getLogger(__name__)


@dataclass
class SchedulerStats:
    """Statistics for the scheduler with bounded error history."""
    total_checks: int = 0
    successful_checks: int = 0
    failed_checks: int = 0
    products_found: int = 0
    alerts_sent: int = 0
    last_check: Optional[datetime] = None
    errors: List[str] = field(default_factory=list)
    max_errors: int = 100  # Prevent unbounded growth
    
    def add_error(self, error: str) -> None:
        """Add error with automatic pruning of old errors."""
        self.errors.append(error)
        # Keep only last max_errors to prevent memory leak
        if len(self.errors) > self.max_errors:
            self.errors = self.errors[-self.max_errors:]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'total_checks': self.total_checks,
            'successful_checks': self.successful_checks,
            'failed_checks': self.failed_checks,
            'products_found': self.products_found,
            'alerts_sent': self.alerts_sent,
            'last_check': self.last_check.isoformat() if self.last_check else None,
            'recent_errors': self.errors[-10:] if self.errors else [],
            'total_errors': len(self.errors),
        }


class StockScheduler:
    """Scheduler for monitoring stock across all retailers."""
    
    def __init__(
        self,
        bot: discord.Client,
        db: Database,
        alert_callback: Optional[Callable[[StockAlert], None]] = None
    ):
        self.bot = bot
        self.db = db
        self.alert_callback = alert_callback
        self.running = False
        self._monitoring_task: Optional[asyncio.Task] = None
        self._stats = SchedulerStats()
        
        # Initialize scrapers
        self.scrapers = {
            'eb_games': EBGamesScraper(),
            'jb_hifi': JBHiFiScraper(),
            'target': TargetScraper(),
            'big_w': BigWScraper(),
            'kmart': KmartScraper(),
        }
    
    async def start(self):
        """Start the scheduler."""
        self.running = True
        metrics.gauge('scheduler_running').set(1)
        logger.info("Starting stock monitoring scheduler...")
        await self._check_all_retailers()
        self._monitoring_task = asyncio.create_task(self._monitoring_loop())
        logger.info(f"Scheduler started. Checking every {CHECK_INTERVAL} seconds")

    async def stop(self):
        """Stop the scheduler gracefully."""
        self.running = False
        metrics.gauge('scheduler_running').set(0)
        logger.info("Stopping scheduler...")

        if self._monitoring_task and not self._monitoring_task.done():
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass

        for scraper in self.scrapers.values():
            if scraper.session:
                await scraper.session.close()

        logger.info("Scheduler stopped")
    
    async def _monitoring_loop(self):
        """Main monitoring loop."""
        while self.running:
            try:
                await asyncio.sleep(CHECK_INTERVAL)
                if not self.running:
                    break
                await self._check_all_retailers()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}", exc_info=True)
                self._stats.add_error(f"{datetime.now()}: {str(e)}")
                await asyncio.sleep(60)
    
    async def _check_all_retailers(self):
        """Check stock for all enabled retailers concurrently."""
        import time
        start_time = time.time()
        
        logger.info(f"Starting stock check at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self._stats.total_checks += 1
        metrics.counter('stock_checks_total').inc()
        
        all_products: List[Product] = []
        check_tasks = []
        
        for retailer_key, config in RETAILERS.items():
            if not config.enabled:
                continue
            task = asyncio.create_task(
                self._check_retailer(retailer_key, config),
                name=f"check_{retailer_key}"
            )
            check_tasks.append((retailer_key, task))
        
        for retailer_key, task in check_tasks:
            try:
                products = await task
                all_products.extend(products)
                self._stats.successful_checks += 1
            except Exception as e:
                logger.error(f"Error checking {retailer_key}: {e}")
                self._stats.failed_checks += 1
                metrics.counter('scraper_errors_total').inc()
                self._stats.add_error(f"{datetime.now()}: {retailer_key} - {str(e)}")
        
        self._stats.products_found = len(all_products)
        self._stats.last_check = datetime.now()
        
        # Record metrics
        duration = time.time() - start_time
        metrics.histogram('stock_check_duration_seconds').observe(duration)
        metrics.gauge('products_tracked').set(len(all_products))
        
        # Update in-stock gauge
        in_stock_count = sum(1 for p in all_products if p.in_stock)
        metrics.gauge('products_in_stock').set(in_stock_count)
        
        logger.info(f"Completed check. Total products: {len(all_products)} ({in_stock_count} in stock)")
        
        # Cleanup old history daily
        if self._stats.total_checks % (24 * 3600 // CHECK_INTERVAL) == 0:
            try:
                deleted = await self.db.cleanup_old_history(days=30)
                logger.info(f"Cleaned up {deleted} old history entries")
            except Exception as e:
                logger.error(f"Error cleaning up history: {e}")
    
    async def _check_retailer(self, retailer_key: str, config) -> List[Product]:
        """Check a single retailer with concurrent searches."""
        logger.info(f"Checking {config.name}...")
        scraper = self.scrapers.get(retailer_key)
        if not scraper:
            logger.warning(f"No scraper found for {retailer_key}")
            return []
        
        products = []
        async with scraper:
            # Run Pokemon and One Piece searches concurrently
            pokemon_task = scraper.search_products('pokemon booster box')
            onepiece_task = scraper.search_products('one piece booster box')
            
            pokemon_products, onepiece_products = await asyncio.gather(
                pokemon_task, 
                onepiece_task,
                return_exceptions=True
            )
            
            # Handle exceptions
            all_products = []
            if isinstance(pokemon_products, Exception):
                logger.error(f"Error searching Pokemon on {config.name}: {pokemon_products}")
            else:
                all_products.extend(pokemon_products)
            
            if isinstance(onepiece_products, Exception):
                logger.error(f"Error searching One Piece on {config.name}: {onepiece_products}")
            else:
                all_products.extend(onepiece_products)
            
            # Process all products concurrently
            await asyncio.gather(*[
                self._process_product(product) 
                for product in all_products
            ], return_exceptions=True)
            
            products.extend(all_products)
            logger.info(f"  {config.name}: Found {len(all_products)} booster boxes")
        
        return products
    
    async def _process_product(self, product: Product):
        """Process a product and check for stock changes."""
        try:
            product.last_checked = datetime.now()
            previous = await self.db.get_product(product.id)
            
            if previous:
                if product.in_stock and not previous.in_stock:
                    logger.info(f"STOCK ALERT: {product.name} at {product.retailer}")
                    
                    if not await self.db.should_send_alert(product.id, ALERT_COOLDOWN):
                        logger.debug(f"Alert cooldown active for {product.name}, skipping")
                        return
                    
                    product.last_in_stock = datetime.now()
                    alert = StockAlert(
                        product=product,
                        alert_type=AlertType.IN_STOCK,
                        timestamp=datetime.now(),
                        previous_status=previous.in_stock,
                        message=f"Back in stock at {product.retailer}!"
                    )
                    
                    alert_id = await self.db.save_alert(alert)
                    await self._send_alert(alert)
                    await self.db.mark_alert_sent(alert_id)
                    self._stats.alerts_sent += 1
                
                elif product.price != previous.price and product.price is not None:
                    logger.info(f"Price change: {product.name} ${previous.price} -> ${product.price}")
                    alert = StockAlert(
                        product=product,
                        alert_type=AlertType.PRICE_CHANGE,
                        timestamp=datetime.now(),
                        previous_price=previous.price
                    )
                    await self.db.save_alert(alert)
            else:
                logger.info(f"New product: {product.name} at {product.retailer}")
                if product.in_stock:
                    product.last_in_stock = datetime.now()
            
            await self.db.save_product(product)
            await self.db.save_stock_history(product)
        
        except Exception as e:
            logger.error(f"Error processing product {product.name}: {e}", exc_info=True)
    
    async def _send_alert(self, alert: StockAlert):
        """Send Discord alert for stock change."""
        import time
        if self.alert_callback:
            try:
                start_time = time.time()
                success = await self.alert_callback(alert)
                duration = time.time() - start_time
                
                metrics.histogram('alert_send_duration_seconds').observe(duration)
                
                if success:
                    metrics.counter('alerts_sent_total').inc()
                else:
                    metrics.counter('alerts_failed_total').inc()
            except Exception as e:
                metrics.counter('alerts_failed_total').inc()
                logger.error(f"Error sending alert: {e}", exc_info=True)
    
    async def force_check(self) -> List[Product]:
        """Force an immediate stock check."""
        logger.info("Forcing immediate stock check...")
        await self._check_all_retailers()
        return await self.db.get_all_products()
    
    def get_status(self) -> dict:
        """Get scheduler status."""
        return {
            'running': self.running,
            'stats': self._stats.to_dict(),
            'check_interval': CHECK_INTERVAL,
            'retailers': len([r for r in RETAILERS.values() if r.enabled]),
        }
