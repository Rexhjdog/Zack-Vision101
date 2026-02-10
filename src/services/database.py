"""Async database operations for Zack Vision."""
import os
import aiosqlite
import sqlite3
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from contextlib import asynccontextmanager
import logging

from src.config import DATABASE_PATH, DATABASE_WAL_MODE
from src.models.product import Product, StockAlert, TrackedProduct, AlertType, StockHistory

logger = logging.getLogger(__name__)


class Database:
    """Async database operations with SQLite."""
    
    def __init__(self, db_path: str = DATABASE_PATH):
        self.db_path = db_path
        self._connection: Optional[aiosqlite.Connection] = None
    
    async def connect(self):
        """Initialize database connection."""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        self._connection = await aiosqlite.connect(self.db_path)
        
        if DATABASE_WAL_MODE:
            await self._connection.execute('PRAGMA journal_mode=WAL')
            await self._connection.execute('PRAGMA synchronous=NORMAL')
        
        await self._create_tables()
        await self._create_indexes()
        logger.info("Database connected successfully")
    
    async def close(self):
        """Close database connection."""
        if self._connection:
            await self._connection.close()
            logger.info("Database connection closed")
    
    @asynccontextmanager
    async def transaction(self):
        """Async context manager for database transactions."""
        if not self._connection:
            await self.connect()
        
        try:
            yield self._connection
            await self._connection.commit()
        except Exception:
            await self._connection.rollback()
            raise
    
    async def _create_tables(self):
        """Create database tables if they don't exist."""
        await self._connection.execute('''
            CREATE TABLE IF NOT EXISTS products (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                retailer TEXT NOT NULL,
                url TEXT NOT NULL,
                price REAL,
                currency TEXT DEFAULT 'AUD',
                in_stock INTEGER DEFAULT 0,
                image_url TEXT,
                category TEXT,
                set_name TEXT,
                pack_type TEXT DEFAULT 'box',
                last_checked TEXT,
                last_in_stock TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        await self._connection.execute('''
            CREATE TABLE IF NOT EXISTS stock_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id TEXT NOT NULL,
                in_stock INTEGER NOT NULL,
                price REAL,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
            )
        ''')
        
        await self._connection.execute('''
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id TEXT NOT NULL,
                alert_type TEXT NOT NULL,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                previous_status INTEGER,
                previous_price REAL,
                message TEXT,
                sent INTEGER DEFAULT 0,
                FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
            )
        ''')
        
        await self._connection.execute('''
            CREATE TABLE IF NOT EXISTS tracked_products (
                id TEXT PRIMARY KEY,
                url TEXT NOT NULL,
                name TEXT,
                added_by INTEGER,
                added_at TEXT DEFAULT CURRENT_TIMESTAMP,
                enabled INTEGER DEFAULT 1,
                alert_channel_id INTEGER
            )
        ''')
        
        await self._connection.execute('''
            CREATE TABLE IF NOT EXISTS user_preferences (
                user_id INTEGER PRIMARY KEY,
                alerts_enabled INTEGER DEFAULT 1,
                alert_types TEXT DEFAULT '["in_stock"]',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        await self._connection.commit()
    
    async def _create_indexes(self):
        """Create database indexes for better performance."""
        indexes = [
            'CREATE INDEX IF NOT EXISTS idx_products_retailer ON products(retailer)',
            'CREATE INDEX IF NOT EXISTS idx_products_in_stock ON products(in_stock)',
            'CREATE INDEX IF NOT EXISTS idx_products_category ON products(category)',
            'CREATE INDEX IF NOT EXISTS idx_stock_history_product ON stock_history(product_id)',
            'CREATE INDEX IF NOT EXISTS idx_stock_history_timestamp ON stock_history(timestamp)',
            'CREATE INDEX IF NOT EXISTS idx_alerts_product ON alerts(product_id)',
            'CREATE INDEX IF NOT EXISTS idx_alerts_timestamp ON alerts(timestamp)',
            'CREATE INDEX IF NOT EXISTS idx_alerts_sent ON alerts(sent)',
            'CREATE INDEX IF NOT EXISTS idx_tracked_enabled ON tracked_products(enabled)',
        ]
        
        for index_sql in indexes:
            await self._connection.execute(index_sql)
        
        await self._connection.commit()
    
    async def save_product(self, product: Product) -> None:
        """Save or update a product."""
        async with self.transaction() as conn:
            await conn.execute('''
                INSERT OR REPLACE INTO products 
                (id, name, retailer, url, price, currency, in_stock, image_url, 
                 category, set_name, pack_type, last_checked, last_in_stock)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                product.id, product.name, product.retailer, product.url,
                product.price, product.currency, int(product.in_stock),
                product.image_url, product.category, product.set_name,
                product.pack_type,
                product.last_checked.isoformat() if product.last_checked else None,
                product.last_in_stock.isoformat() if product.last_in_stock else None
            ))
    
    async def get_product(self, product_id: str) -> Optional[Product]:
        """Get a product by ID."""
        async with self._connection.execute(
            'SELECT * FROM products WHERE id = ?', (product_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return self._row_to_product(row)
            return None
    
    async def get_all_products(self, limit: int = 1000, offset: int = 0) -> List[Product]:
        """Get all tracked products with pagination.
        
        Args:
            limit: Maximum number of products to return (default: 1000)
            offset: Number of products to skip (default: 0)
        """
        async with self._connection.execute(
            'SELECT * FROM products LIMIT ? OFFSET ?', (limit, offset)
        ) as cursor:
            rows = await cursor.fetchall()
            return [self._row_to_product(row) for row in rows]
    
    async def get_products_by_retailer(self, retailer: str, limit: int = 1000, offset: int = 0) -> List[Product]:
        """Get products for a specific retailer with pagination.
        
        Args:
            retailer: The retailer name to filter by
            limit: Maximum number of products to return (default: 1000)
            offset: Number of products to skip (default: 0)
        """
        async with self._connection.execute(
            'SELECT * FROM products WHERE retailer = ? LIMIT ? OFFSET ?', 
            (retailer, limit, offset)
        ) as cursor:
            rows = await cursor.fetchall()
            return [self._row_to_product(row) for row in rows]
    
    async def get_in_stock_products(self, limit: int = 1000, offset: int = 0) -> List[Product]:
        """Get all products currently in stock with pagination.
        
        Args:
            limit: Maximum number of products to return (default: 1000)
            offset: Number of products to skip (default: 0)
        """
        async with self._connection.execute(
            'SELECT * FROM products WHERE in_stock = 1 LIMIT ? OFFSET ?',
            (limit, offset)
        ) as cursor:
            rows = await cursor.fetchall()
            return [self._row_to_product(row) for row in rows]
    
    async def get_product_count(self) -> int:
        """Get total number of products."""
        async with self._connection.execute('SELECT COUNT(*) FROM products') as cursor:
            result = await cursor.fetchone()
            return result[0] if result else 0
    
    async def save_stock_history(self, product: Product) -> None:
        """Save stock history entry."""
        async with self.transaction() as conn:
            await conn.execute('''
                INSERT INTO stock_history (product_id, in_stock, price, timestamp)
                VALUES (?, ?, ?, ?)
            ''', (
                product.id,
                int(product.in_stock),
                product.price,
                datetime.now().isoformat()
            ))
    
    async def save_alert(self, alert: StockAlert) -> int:
        """Save an alert and return the alert ID."""
        async with self.transaction() as conn:
            cursor = await conn.execute('''
                INSERT INTO alerts 
                (product_id, alert_type, timestamp, previous_status, previous_price, message, sent)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                alert.product.id,
                alert.alert_type.value,
                alert.timestamp.isoformat(),
                int(alert.previous_status) if alert.previous_status is not None else None,
                alert.previous_price,
                alert.message,
                int(alert.sent)
            ))
            return cursor.lastrowid
    
    async def mark_alert_sent(self, alert_id: int) -> None:
        """Mark an alert as sent."""
        async with self.transaction() as conn:
            await conn.execute(
                'UPDATE alerts SET sent = 1 WHERE id = ?',
                (alert_id,)
            )
    
    async def get_recent_alerts(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Get alerts from the last N hours."""
        cutoff_time = (datetime.now() - timedelta(hours=hours)).isoformat()
        
        async with self._connection.execute('''
            SELECT a.*, p.name, p.retailer, p.url 
            FROM alerts a
            JOIN products p ON a.product_id = p.id
            WHERE a.timestamp > ?
            ORDER BY a.timestamp DESC
        ''', (cutoff_time,)) as cursor:
            rows = await cursor.fetchall()
            columns = [description[0] for description in cursor.description]
            return [dict(zip(columns, row)) for row in rows]
    
    async def add_tracked_product(self, tracked: TrackedProduct) -> None:
        """Add a user-tracked product."""
        async with self.transaction() as conn:
            await conn.execute('''
                INSERT OR REPLACE INTO tracked_products
                (id, url, name, added_by, added_at, enabled, alert_channel_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                tracked.id, tracked.url, tracked.name, tracked.added_by,
                tracked.added_at.isoformat() if tracked.added_at else None,
                int(tracked.enabled), tracked.alert_channel_id
            ))
    
    async def get_tracked_products(self) -> List[TrackedProduct]:
        """Get all user-tracked products."""
        async with self._connection.execute(
            'SELECT * FROM tracked_products WHERE enabled = 1'
        ) as cursor:
            rows = await cursor.fetchall()
            return [self._row_to_tracked_product(row) for row in rows]
    
    async def remove_tracked_product(self, product_id: str) -> None:
        """Remove a tracked product."""
        async with self.transaction() as conn:
            await conn.execute(
                'DELETE FROM tracked_products WHERE id = ?',
                (product_id,)
            )
    
    async def get_last_alert_time(self, product_id: str, alert_type: AlertType = AlertType.IN_STOCK) -> Optional[datetime]:
        """Get the timestamp of the last alert for a product."""
        async with self._connection.execute('''
            SELECT timestamp FROM alerts 
            WHERE product_id = ? AND alert_type = ?
            ORDER BY timestamp DESC 
            LIMIT 1
        ''', (product_id, alert_type.value)) as cursor:
            row = await cursor.fetchone()
            if row and row[0]:
                return datetime.fromisoformat(row[0])
            return None
    
    async def should_send_alert(self, product_id: str, cooldown_seconds: int = 300) -> bool:
        """Check if enough time has passed since the last alert."""
        last_alert = await self.get_last_alert_time(product_id)
        if not last_alert:
            return True
        
        time_since_last = datetime.now() - last_alert
        return time_since_last > timedelta(seconds=cooldown_seconds)
    
    async def cleanup_old_history(self, days: int = 30) -> int:
        """Remove stock history older than specified days. Returns number of rows deleted."""
        cutoff_time = (datetime.now() - timedelta(days=days)).isoformat()
        
        async with self.transaction() as conn:
            cursor = await conn.execute(
                'DELETE FROM stock_history WHERE timestamp < ?',
                (cutoff_time,)
            )
            return cursor.rowcount
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get database statistics."""
        async with self._connection.execute(
            'SELECT COUNT(*) FROM products'
        ) as cursor:
            total_products = (await cursor.fetchone())[0]
        
        async with self._connection.execute(
            'SELECT COUNT(*) FROM products WHERE in_stock = 1'
        ) as cursor:
            in_stock = (await cursor.fetchone())[0]
        
        async with self._connection.execute(
            'SELECT COUNT(*) FROM alerts WHERE timestamp > ?',
            ((datetime.now() - timedelta(days=1)).isoformat(),)
        ) as cursor:
            alerts_24h = (await cursor.fetchone())[0]
        
        return {
            'total_products': total_products,
            'in_stock': in_stock,
            'alerts_24h': alerts_24h,
        }
    
    def _row_to_product(self, row: sqlite3.Row) -> Product:
        """Convert database row to Product object."""
        return Product(
            id=row[0],
            name=row[1],
            retailer=row[2],
            url=row[3],
            price=row[4],
            currency=row[5] or 'AUD',
            in_stock=bool(row[6]),
            image_url=row[7],
            category=row[8] or '',
            set_name=row[9],
            pack_type=row[10] or 'box',
            last_checked=datetime.fromisoformat(row[11]) if row[11] else None,
            last_in_stock=datetime.fromisoformat(row[12]) if row[12] else None,
            created_at=datetime.fromisoformat(row[13]) if row[13] else None,
        )
    
    def _row_to_tracked_product(self, row: sqlite3.Row) -> TrackedProduct:
        """Convert database row to TrackedProduct object."""
        return TrackedProduct(
            id=row[0],
            url=row[1],
            name=row[2],
            added_by=row[3],
            added_at=datetime.fromisoformat(row[4]) if row[4] else None,
            enabled=bool(row[5]),
            alert_channel_id=row[6],
        )
