"""Async SQLite database layer."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

import aiosqlite

from src.config import DATABASE_PATH, DATABASE_WAL_MODE, HISTORY_RETENTION_DAYS
from src.models.product import (
    AlertType,
    Product,
    StockAlert,
    StockHistory,
    TrackedProduct,
)

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Schema
# ------------------------------------------------------------------

_SCHEMA = """\
CREATE TABLE IF NOT EXISTS products (
    url          TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    retailer     TEXT NOT NULL,
    in_stock     INTEGER NOT NULL DEFAULT 0,
    price        REAL,
    category     TEXT NOT NULL DEFAULT 'unknown',
    set_name     TEXT NOT NULL DEFAULT '',
    image_url    TEXT NOT NULL DEFAULT '',
    last_checked TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS stock_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    product_url TEXT NOT NULL,
    retailer    TEXT NOT NULL,
    in_stock    INTEGER NOT NULL,
    price       REAL,
    recorded_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS alerts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    product_url TEXT NOT NULL,
    alert_type  TEXT NOT NULL,
    old_price   REAL,
    new_price   REAL,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tracked_products (
    url       TEXT PRIMARY KEY,
    name      TEXT NOT NULL DEFAULT '',
    added_by  INTEGER NOT NULL DEFAULT 0,
    retailer  TEXT NOT NULL DEFAULT '',
    added_at  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_history_url     ON stock_history(product_url);
CREATE INDEX IF NOT EXISTS idx_history_date    ON stock_history(recorded_at);
CREATE INDEX IF NOT EXISTS idx_alerts_date     ON alerts(created_at);
CREATE INDEX IF NOT EXISTS idx_products_retail ON products(retailer);
"""


class Database:
    """Async wrapper around SQLite for product / alert persistence."""

    def __init__(self, db_path: str = DATABASE_PATH) -> None:
        self._db_path = db_path
        self._conn: aiosqlite.Connection | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = await aiosqlite.connect(self._db_path)
        self._conn.row_factory = aiosqlite.Row

        if DATABASE_WAL_MODE:
            await self._conn.execute("PRAGMA journal_mode=WAL")
            await self._conn.execute("PRAGMA synchronous=NORMAL")

        await self._conn.executescript(_SCHEMA)
        await self._conn.commit()
        logger.info("Database connected: %s", self._db_path)

    async def close(self) -> None:
        if self._conn:
            await self._conn.close()
            self._conn = None
            logger.info("Database connection closed")

    @property
    def conn(self) -> aiosqlite.Connection:
        if self._conn is None:
            raise RuntimeError("Database not connected – call connect() first")
        return self._conn

    # ------------------------------------------------------------------
    # Products
    # ------------------------------------------------------------------

    async def upsert_product(self, product: Product) -> None:
        await self.conn.execute(
            """
            INSERT INTO products (url, name, retailer, in_stock, price,
                                  category, set_name, image_url, last_checked)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(url) DO UPDATE SET
                name=excluded.name,
                in_stock=excluded.in_stock,
                price=excluded.price,
                category=excluded.category,
                set_name=excluded.set_name,
                image_url=excluded.image_url,
                last_checked=excluded.last_checked
            """,
            (
                product.url,
                product.name,
                product.retailer,
                int(product.in_stock),
                product.price,
                product.category,
                product.set_name,
                product.image_url,
                product.last_checked.isoformat(),
            ),
        )
        await self.conn.commit()

    async def get_product(self, url: str) -> Product | None:
        async with self.conn.execute(
            "SELECT * FROM products WHERE url = ?", (url,)
        ) as cur:
            row = await cur.fetchone()
            if row is None:
                return None
            return self._row_to_product(row)

    async def get_products_by_retailer(self, retailer: str) -> list[Product]:
        async with self.conn.execute(
            "SELECT * FROM products WHERE retailer = ? ORDER BY name",
            (retailer,),
        ) as cur:
            return [self._row_to_product(r) async for r in cur]

    async def get_all_products(self) -> list[Product]:
        async with self.conn.execute(
            "SELECT * FROM products ORDER BY retailer, name"
        ) as cur:
            return [self._row_to_product(r) async for r in cur]

    async def get_in_stock_count(self) -> int:
        async with self.conn.execute(
            "SELECT COUNT(*) FROM products WHERE in_stock = 1"
        ) as cur:
            row = await cur.fetchone()
            return row[0] if row else 0

    async def get_total_product_count(self) -> int:
        async with self.conn.execute("SELECT COUNT(*) FROM products") as cur:
            row = await cur.fetchone()
            return row[0] if row else 0

    # ------------------------------------------------------------------
    # Stock history
    # ------------------------------------------------------------------

    async def record_history(self, product: Product) -> None:
        await self.conn.execute(
            """
            INSERT INTO stock_history (product_url, retailer, in_stock, price, recorded_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                product.url,
                product.retailer,
                int(product.in_stock),
                product.price,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        await self.conn.commit()

    async def cleanup_old_history(self) -> int:
        cutoff = (
            datetime.now(timezone.utc) - timedelta(days=HISTORY_RETENTION_DAYS)
        ).isoformat()
        async with self.conn.execute(
            "DELETE FROM stock_history WHERE recorded_at < ?", (cutoff,)
        ) as cur:
            deleted = cur.rowcount
        await self.conn.commit()
        return deleted

    # ------------------------------------------------------------------
    # Alerts
    # ------------------------------------------------------------------

    async def record_alert(self, alert: StockAlert) -> None:
        await self.conn.execute(
            """
            INSERT INTO alerts (product_url, alert_type, old_price, new_price, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                alert.product.url,
                alert.alert_type.value,
                alert.previous_price,
                alert.product.price,
                alert.timestamp.isoformat(),
            ),
        )
        await self.conn.commit()

    async def get_recent_alert_count(self, hours: int = 24) -> int:
        cutoff = (
            datetime.now(timezone.utc) - timedelta(hours=hours)
        ).isoformat()
        async with self.conn.execute(
            "SELECT COUNT(*) FROM alerts WHERE created_at >= ?", (cutoff,)
        ) as cur:
            row = await cur.fetchone()
            return row[0] if row else 0

    async def was_recently_alerted(self, url: str, cooldown_secs: int) -> bool:
        cutoff = (
            datetime.now(timezone.utc) - timedelta(seconds=cooldown_secs)
        ).isoformat()
        async with self.conn.execute(
            "SELECT COUNT(*) FROM alerts WHERE product_url = ? AND created_at >= ?",
            (url, cutoff),
        ) as cur:
            row = await cur.fetchone()
            return (row[0] if row else 0) > 0

    # ------------------------------------------------------------------
    # Tracked products
    # ------------------------------------------------------------------

    async def add_tracked(self, tp: TrackedProduct) -> None:
        await self.conn.execute(
            """
            INSERT OR IGNORE INTO tracked_products (url, name, added_by, retailer, added_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (tp.url, tp.name, tp.added_by, tp.retailer, tp.added_at.isoformat()),
        )
        await self.conn.commit()

    async def get_all_tracked(self) -> list[TrackedProduct]:
        async with self.conn.execute(
            "SELECT * FROM tracked_products ORDER BY added_at DESC"
        ) as cur:
            rows = await cur.fetchall()
            return [
                TrackedProduct(
                    url=r["url"],
                    name=r["name"],
                    added_by=r["added_by"],
                    retailer=r["retailer"],
                    added_at=datetime.fromisoformat(r["added_at"]),
                )
                for r in rows
            ]

    async def remove_tracked(self, url: str) -> bool:
        async with self.conn.execute(
            "DELETE FROM tracked_products WHERE url = ?", (url,)
        ) as cur:
            deleted = cur.rowcount > 0
        await self.conn.commit()
        return deleted

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_product(row: aiosqlite.Row) -> Product:
        return Product(
            name=row["name"],
            url=row["url"],
            retailer=row["retailer"],
            in_stock=bool(row["in_stock"]),
            price=row["price"],
            category=row["category"],
            set_name=row["set_name"],
            image_url=row["image_url"],
            last_checked=datetime.fromisoformat(row["last_checked"]),
        )
