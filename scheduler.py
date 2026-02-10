import asyncio
import logging
from datetime import datetime
from typing import List, Optional, Callable, Awaitable
from config import CHECK_INTERVAL, ERROR_RETRY_INTERVAL, RETAILERS, ALERT_COOLDOWN
from database import Database
from models import Product, StockAlert
from scrapers import (
    EBGamesScraper,
    JBHiFiScraper,
    TargetScraper,
    BigWScraper,
    KmartScraper,
)

logger = logging.getLogger(__name__)

# Type alias for the alert callback
AlertCallback = Callable[[Product], Awaitable[None]]


class StockScheduler:
    """Scheduler for checking stock across all retailers.

    Accepts an alert_callback to decouple from the bot module,
    eliminating the previous circular import.
    """

    def __init__(self, db: Database, alert_callback: AlertCallback):
        self.db = db
        self._alert_callback = alert_callback
        self.running = False
        self.last_check: Optional[datetime] = None
        self._monitoring_task: Optional[asyncio.Task] = None

        self.scrapers = {
            'eb_games': EBGamesScraper(),
            'jb_hifi': JBHiFiScraper(),
            'target': TargetScraper(),
            'big_w': BigWScraper(),
            'kmart': KmartScraper(),
        }

    async def start(self):
        """Start the scheduler"""
        self.running = True
        logger.info("Starting stock monitoring scheduler...")
        self._monitoring_task = asyncio.create_task(self._monitoring_loop())

    async def stop(self):
        """Stop the scheduler gracefully"""
        self.running = False
        logger.info("Stopping stock monitoring scheduler...")

        if self._monitoring_task and not self._monitoring_task.done():
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass

        logger.info("Scheduler stopped successfully")

    async def _monitoring_loop(self):
        """Main monitoring loop"""
        while self.running:
            try:
                logger.info(f"Checking stock at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                await self._check_all_retailers()
                self.last_check = datetime.now()

                # Periodic cleanup of old stock history
                self.db.cleanup_old_history()

                await asyncio.sleep(CHECK_INTERVAL)

            except asyncio.CancelledError:
                logger.info("Monitoring loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}", exc_info=True)
                await asyncio.sleep(ERROR_RETRY_INTERVAL)

    async def _check_single_retailer(self, retailer_key: str, config: dict) -> List[Product]:
        """Check stock for a single retailer"""
        scraper = self.scrapers.get(retailer_key)
        if not scraper:
            logger.warning(f"No scraper found for {retailer_key}")
            return []

        all_products = []
        try:
            logger.info(f"  Checking {config['name']}...")
            async with scraper:
                pokemon_products = await scraper.search_products('pokemon booster box')
                onepiece_products = await scraper.search_products('one piece booster box')
                all_products = pokemon_products + onepiece_products

                for product in all_products:
                    await self._process_product(product)

                logger.info(f"    Found {len(all_products)} products from {config['name']}")

        except Exception as e:
            logger.error(f"    Error checking {config['name']}: {e}", exc_info=True)

        return all_products

    async def _check_all_retailers(self):
        """Check stock for all enabled retailers concurrently"""
        enabled_retailers = {
            key: config for key, config in RETAILERS.items()
            if config.get('enabled', True)
        }

        # Run all retailer checks concurrently
        tasks = [
            self._check_single_retailer(key, config)
            for key, config in enabled_retailers.items()
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        total = 0
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Retailer check failed: {result}")
            elif isinstance(result, list):
                total += len(result)

        logger.info(f"Completed check. Total products: {total}")

    async def _process_product(self, product: Product):
        """Process a product and check for stock changes"""
        try:
            product.last_checked = datetime.now()
            previous = self.db.get_product(product.id)

            if previous:
                # Check for stock status change: out-of-stock -> in-stock
                if product.in_stock and not previous.in_stock:
                    logger.info(f"STOCK ALERT: {product.name} at {product.retailer}")

                    if not self.db.should_send_alert(product.id, ALERT_COOLDOWN):
                        logger.debug(f"Alert cooldown active for {product.name}, skipping")
                    else:
                        product.last_in_stock = datetime.now()
                        alert = StockAlert(
                            product=product,
                            alert_type='in_stock',
                            timestamp=datetime.now(),
                            previous_status=previous.in_stock,
                            message=f"Back in stock at {product.retailer}!"
                        )
                        self.db.save_alert(alert)
                        await self._send_alert(alert)

                # Check for price change
                elif product.price != previous.price and product.price is not None:
                    logger.info(f"Price change: {product.name} ${previous.price} -> ${product.price}")
                    alert = StockAlert(
                        product=product,
                        alert_type='price_change',
                        timestamp=datetime.now(),
                        previous_price=previous.price
                    )
                    self.db.save_alert(alert)
            else:
                # New product discovered
                logger.info(f"New product: {product.name} at {product.retailer}")
                if product.in_stock:
                    product.last_in_stock = datetime.now()

            self.db.save_product(product)
            self.db.save_stock_history(product)

        except Exception as e:
            logger.error(f"Error processing product {product.name}: {e}", exc_info=True)

    async def _send_alert(self, alert: StockAlert):
        """Send alert via the injected callback (no circular import)"""
        try:
            await self._alert_callback(alert.product)
        except Exception as e:
            logger.error(f"Error sending Discord alert: {e}", exc_info=True)

    async def force_check(self) -> List[Product]:
        """Force an immediate stock check"""
        logger.info("Forcing immediate stock check...")
        await self._check_all_retailers()
        return self.db.get_all_products()

    def get_status(self) -> dict:
        """Get scheduler status"""
        return {
            'running': self.running,
            'last_check': self.last_check,
            'check_interval': CHECK_INTERVAL,
            'retailers': len([r for r in RETAILERS.values() if r.get('enabled')]),
        }
