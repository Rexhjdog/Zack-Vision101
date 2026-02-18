"""Stock-monitoring scheduler.

Periodically scrapes all configured retailers and emits alerts when stock
status changes.
"""

from __future__ import annotations

import asyncio
import logging
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Coroutine

import aiohttp

from src.config import ALERT_COOLDOWN, CHECK_INTERVAL, RETAILERS
from src.models.product import AlertType, Product, StockAlert
from src.scrapers import SCRAPER_MAP
from src.services.database import Database

logger = logging.getLogger(__name__)

AlertCallback = Callable[[StockAlert], Coroutine]


@dataclass
class SchedulerStats:
    total_checks: int = 0
    successful_checks: int = 0
    failed_checks: int = 0
    products_found: int = 0
    alerts_sent: int = 0
    last_check: datetime | None = None
    errors: deque[str] = field(default_factory=lambda: deque(maxlen=100))


class StockScheduler:
    """Runs an async loop that checks all retailers on a fixed interval."""

    def __init__(self, db: Database, on_alert: AlertCallback | None = None) -> None:
        self._db = db
        self._on_alert = on_alert
        self._running = False
        self._task: asyncio.Task | None = None
        self.stats = SchedulerStats()

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    @property
    def is_running(self) -> bool:
        return self._running

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("Scheduler started (interval=%ds)", CHECK_INTERVAL)

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("Scheduler stopped")

    async def run_once(self) -> list[StockAlert]:
        """Execute one full check cycle and return generated alerts."""
        return await self._check_all()

    # ------------------------------------------------------------------
    # Internal loop
    # ------------------------------------------------------------------

    async def _loop(self) -> None:
        while self._running:
            try:
                await self._check_all()
            except Exception as exc:
                logger.exception("Scheduler loop error: %s", exc)
                self.stats.errors.append(
                    f"{datetime.now(timezone.utc).isoformat()} loop: {exc}"
                )
            await asyncio.sleep(CHECK_INTERVAL)

    async def _check_all(self) -> list[StockAlert]:
        """Check every retailer concurrently."""
        self.stats.total_checks += 1
        self.stats.last_check = datetime.now(timezone.utc)
        alerts: list[StockAlert] = []

        async with aiohttp.ClientSession() as session:
            tasks = []
            for key, cfg in RETAILERS.items():
                if key not in SCRAPER_MAP:
                    continue
                tasks.append(self._check_retailer(key, cfg, session))
            results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, Exception):
                self.stats.failed_checks += 1
                self.stats.errors.append(
                    f"{datetime.now(timezone.utc).isoformat()} {result}"
                )
            elif isinstance(result, list):
                self.stats.successful_checks += 1
                alerts.extend(result)

        # Periodic history cleanup
        if self.stats.total_checks % 50 == 0:
            deleted = await self._db.cleanup_old_history()
            if deleted:
                logger.info("Cleaned up %d old history records", deleted)

        return alerts

    async def _check_retailer(
        self,
        key: str,
        cfg: dict,
        session: aiohttp.ClientSession,
    ) -> list[StockAlert]:
        """Scrape one retailer for both pokemon and one_piece."""
        scraper = SCRAPER_MAP[key]()
        search_paths: dict = cfg.get("search_paths", {})
        alerts: list[StockAlert] = []

        # Search each category concurrently
        cat_tasks = [
            scraper.search(cat, path, session=session)
            for cat, path in search_paths.items()
        ]
        results = await asyncio.gather(*cat_tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, Exception):
                logger.warning("[%s] Category search failed: %s", cfg["name"], result)
                continue
            if not isinstance(result, list):
                continue

            self.stats.products_found += len(result)
            for product in result:
                new_alerts = await self._process_product(product)
                alerts.extend(new_alerts)

        return alerts

    async def _process_product(self, product: Product) -> list[StockAlert]:
        """Compare against DB state, persist, and emit alerts."""
        alerts: list[StockAlert] = []
        existing = await self._db.get_product(product.url)

        if existing is None:
            # New product
            await self._db.upsert_product(product)
            await self._db.record_history(product)
            if product.in_stock:
                alert = StockAlert(product=product, alert_type=AlertType.NEW_PRODUCT)
                alerts.append(alert)
        else:
            # Stock transition: out -> in
            if product.in_stock and not existing.in_stock:
                alert = StockAlert(product=product, alert_type=AlertType.IN_STOCK)
                alerts.append(alert)
            # Stock transition: in -> out
            elif not product.in_stock and existing.in_stock:
                alert = StockAlert(product=product, alert_type=AlertType.OUT_OF_STOCK)
                alerts.append(alert)
            # Price change
            if (
                product.price is not None
                and existing.price is not None
                and product.price != existing.price
            ):
                alert = StockAlert(
                    product=product,
                    alert_type=AlertType.PRICE_CHANGE,
                    previous_price=existing.price,
                )
                alerts.append(alert)

            await self._db.upsert_product(product)
            await self._db.record_history(product)

        # Deliver alerts
        for alert in alerts:
            if await self._db.was_recently_alerted(
                alert.product.url, ALERT_COOLDOWN
            ):
                continue
            await self._db.record_alert(alert)
            self.stats.alerts_sent += 1
            if self._on_alert:
                try:
                    await self._on_alert(alert)
                except Exception as exc:
                    logger.error("Alert callback error: %s", exc)

        return alerts
