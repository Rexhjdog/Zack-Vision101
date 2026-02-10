import sqlite3
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict
from models import Product, StockAlert, TrackedProduct, UserPreference
from config import DATABASE_PATH, STOCK_HISTORY_RETENTION_DAYS

logger = logging.getLogger(__name__)


class Database:
    def __init__(self, db_path: str = DATABASE_PATH):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Get a database connection with WAL mode for better concurrency"""
        conn = sqlite3.connect(self.db_path)
        conn.execute('PRAGMA journal_mode=WAL')
        conn.execute('PRAGMA foreign_keys=ON')
        return conn

    def _init_db(self):
        """Initialize database tables and indexes"""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute('''
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
                    pack_type TEXT,
                    last_checked TEXT,
                    last_in_stock TEXT
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS stock_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_id TEXT NOT NULL,
                    in_stock INTEGER NOT NULL,
                    price REAL,
                    timestamp TEXT NOT NULL,
                    FOREIGN KEY (product_id) REFERENCES products(id)
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_id TEXT NOT NULL,
                    alert_type TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    previous_status INTEGER,
                    previous_price REAL,
                    message TEXT,
                    sent INTEGER DEFAULT 0,
                    FOREIGN KEY (product_id) REFERENCES products(id)
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS tracked_products (
                    id TEXT PRIMARY KEY,
                    url TEXT NOT NULL,
                    name TEXT,
                    added_by INTEGER,
                    added_at TEXT,
                    enabled INTEGER DEFAULT 1,
                    alert_channel_id INTEGER
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_preferences (
                    user_id INTEGER PRIMARY KEY,
                    alerts_enabled INTEGER DEFAULT 1,
                    updated_at TEXT
                )
            ''')

            # Indexes for frequently queried columns
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_stock_history_timestamp
                ON stock_history(timestamp)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_stock_history_product_id
                ON stock_history(product_id)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_alerts_timestamp
                ON alerts(timestamp)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_alerts_product_type
                ON alerts(product_id, alert_type)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_products_retailer
                ON products(retailer)
            ''')

            conn.commit()

    def save_product(self, product: Product):
        """Save or update a product"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
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
            conn.commit()

    def get_product(self, product_id: str) -> Optional[Product]:
        """Get a product by ID"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM products WHERE id = ?', (product_id,))
            row = cursor.fetchone()
            if row:
                return self._row_to_product(row)
            return None

    def get_all_products(self) -> List[Product]:
        """Get all tracked products"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM products')
            rows = cursor.fetchall()
            return [self._row_to_product(row) for row in rows]

    def get_products_by_retailer(self, retailer: str) -> List[Product]:
        """Get products for a specific retailer"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM products WHERE retailer = ?', (retailer,))
            rows = cursor.fetchall()
            return [self._row_to_product(row) for row in rows]

    def save_stock_history(self, product: Product):
        """Save stock history entry"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO stock_history (product_id, in_stock, price, timestamp)
                VALUES (?, ?, ?, ?)
            ''', (
                product.id,
                int(product.in_stock),
                product.price,
                datetime.now().isoformat()
            ))
            conn.commit()

    def save_alert(self, alert: StockAlert):
        """Save an alert"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO alerts
                (product_id, alert_type, timestamp, previous_status, previous_price, message)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                alert.product.id,
                alert.alert_type,
                alert.timestamp.isoformat(),
                int(alert.previous_status) if alert.previous_status is not None else None,
                alert.previous_price,
                alert.message
            ))
            conn.commit()

    def get_recent_alerts(self, hours: int = 24) -> List[Dict]:
        """Get alerts from the last N hours"""
        cutoff_time = (datetime.now() - timedelta(hours=hours)).isoformat()

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT a.*, p.name, p.retailer, p.url
                FROM alerts a
                JOIN products p ON a.product_id = p.id
                WHERE a.timestamp > ?
                ORDER BY a.timestamp DESC
            ''', (cutoff_time,))

            columns = [description[0] for description in cursor.description]
            rows = cursor.fetchall()
            return [dict(zip(columns, row)) for row in rows]

    def add_tracked_product(self, tracked: TrackedProduct):
        """Add a user-tracked product"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO tracked_products
                (id, url, name, added_by, added_at, enabled, alert_channel_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                tracked.id, tracked.url, tracked.name, tracked.added_by,
                tracked.added_at.isoformat() if tracked.added_at else None,
                int(tracked.enabled), tracked.alert_channel_id
            ))
            conn.commit()

    def get_tracked_products(self) -> List[TrackedProduct]:
        """Get all user-tracked products"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM tracked_products WHERE enabled = 1')
            rows = cursor.fetchall()

            products = []
            for row in rows:
                products.append(TrackedProduct(
                    id=row[0],
                    url=row[1],
                    name=row[2],
                    added_by=row[3],
                    added_at=datetime.fromisoformat(row[4]) if row[4] else None,
                    enabled=bool(row[5]),
                    alert_channel_id=row[6]
                ))
            return products

    def remove_tracked_product(self, product_id: str):
        """Remove a tracked product"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM tracked_products WHERE id = ?', (product_id,))
            conn.commit()

    def get_last_alert_time(self, product_id: str, alert_type: str = 'in_stock') -> Optional[datetime]:
        """Get the timestamp of the last alert for a product"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT timestamp FROM alerts
                WHERE product_id = ? AND alert_type = ?
                ORDER BY timestamp DESC
                LIMIT 1
            ''', (product_id, alert_type))
            row = cursor.fetchone()
            if row and row[0]:
                return datetime.fromisoformat(row[0])
            return None

    def should_send_alert(self, product_id: str, cooldown_seconds: int = 300) -> bool:
        """Check if enough time has passed since the last alert"""
        last_alert = self.get_last_alert_time(product_id)
        if not last_alert:
            return True
        time_since_last = datetime.now() - last_alert
        return time_since_last > timedelta(seconds=cooldown_seconds)

    def set_user_preference(self, user_id: int, alerts_enabled: bool):
        """Set a user's alert preference"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO user_preferences
                (user_id, alerts_enabled, updated_at)
                VALUES (?, ?, ?)
            ''', (user_id, int(alerts_enabled), datetime.now().isoformat()))
            conn.commit()

    def get_user_preference(self, user_id: int) -> Optional[UserPreference]:
        """Get a user's alert preference"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT user_id, alerts_enabled, updated_at FROM user_preferences WHERE user_id = ?',
                (user_id,)
            )
            row = cursor.fetchone()
            if row:
                return UserPreference(
                    user_id=row[0],
                    alerts_enabled=bool(row[1]),
                    updated_at=datetime.fromisoformat(row[2]) if row[2] else None
                )
            return None

    def cleanup_old_history(self, retention_days: int = STOCK_HISTORY_RETENTION_DAYS):
        """Remove stock history older than retention period"""
        cutoff = (datetime.now() - timedelta(days=retention_days)).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM stock_history WHERE timestamp < ?', (cutoff,))
            deleted = cursor.rowcount
            conn.commit()
            if deleted > 0:
                logger.info(f"Cleaned up {deleted} old stock history entries")

    def _row_to_product(self, row) -> Product:
        """Convert database row to Product object"""
        return Product(
            id=row[0],
            name=row[1],
            retailer=row[2],
            url=row[3],
            price=row[4],
            currency=row[5],
            in_stock=bool(row[6]),
            image_url=row[7],
            category=row[8],
            set_name=row[9],
            pack_type=row[10],
            last_checked=datetime.fromisoformat(row[11]) if row[11] else None,
            last_in_stock=datetime.fromisoformat(row[12]) if row[12] else None
        )
