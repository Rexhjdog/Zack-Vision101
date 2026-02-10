"""Database migration system for schema versioning."""
import os
import logging
from datetime import datetime
from typing import List, Optional
from dataclasses import dataclass

import aiosqlite

from src.config import DATABASE_PATH

logger = logging.getLogger(__name__)


@dataclass
class Migration:
    """Represents a database migration."""
    version: int
    name: str
    up_sql: str
    down_sql: Optional[str] = None


MIGRATIONS: List[Migration] = [
    Migration(
        version=1,
        name="Initial schema",
        up_sql="""
            CREATE TABLE IF NOT EXISTS schema_version (
                version INTEGER PRIMARY KEY,
                applied_at TEXT DEFAULT CURRENT_TIMESTAMP,
                name TEXT
            );
            
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
            );
            
            CREATE TABLE IF NOT EXISTS stock_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id TEXT NOT NULL,
                in_stock INTEGER NOT NULL,
                price REAL,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
            );
            
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
            );
            
            CREATE TABLE IF NOT EXISTS tracked_products (
                id TEXT PRIMARY KEY,
                url TEXT NOT NULL,
                name TEXT,
                added_by INTEGER,
                added_at TEXT DEFAULT CURRENT_TIMESTAMP,
                enabled INTEGER DEFAULT 1,
                alert_channel_id INTEGER
            );
            
            CREATE TABLE IF NOT EXISTS user_preferences (
                user_id INTEGER PRIMARY KEY,
                alerts_enabled INTEGER DEFAULT 1,
                alert_types TEXT DEFAULT '["in_stock"]',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            
            CREATE INDEX IF NOT EXISTS idx_products_retailer ON products(retailer);
            CREATE INDEX IF NOT EXISTS idx_products_in_stock ON products(in_stock);
            CREATE INDEX IF NOT EXISTS idx_products_category ON products(category);
            CREATE INDEX IF NOT EXISTS idx_stock_history_product ON stock_history(product_id);
            CREATE INDEX IF NOT EXISTS idx_stock_history_timestamp ON stock_history(timestamp);
            CREATE INDEX IF NOT EXISTS idx_alerts_product ON alerts(product_id);
            CREATE INDEX IF NOT EXISTS idx_alerts_timestamp ON alerts(timestamp);
            CREATE INDEX IF NOT EXISTS idx_alerts_sent ON alerts(sent);
            CREATE INDEX IF NOT EXISTS idx_tracked_enabled ON tracked_products(enabled);
        """,
        down_sql="DROP TABLE IF EXISTS schema_version;"
    ),
    Migration(
        version=2,
        name="Add dead letter queue",
        up_sql="""
            CREATE TABLE IF NOT EXISTS failed_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id TEXT NOT NULL,
                alert_type TEXT NOT NULL,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                error_message TEXT,
                retry_count INTEGER DEFAULT 0,
                last_retry TEXT,
                resolved INTEGER DEFAULT 0,
                FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
            );
            
            CREATE INDEX IF NOT EXISTS idx_failed_alerts_resolved ON failed_alerts(resolved);
            CREATE INDEX IF NOT EXISTS idx_failed_alerts_timestamp ON failed_alerts(timestamp);
        """
    ),
    Migration(
        version=3,
        name="Add product metadata",
        up_sql="""
            ALTER TABLE products ADD COLUMN metadata TEXT;
            ALTER TABLE products ADD COLUMN last_price_change TEXT;
        """
    )
]


class MigrationManager:
    """Manages database migrations."""
    
    def __init__(self, db_path: str = DATABASE_PATH):
        self.db_path = db_path
        self.migrations = MIGRATIONS
    
    async def initialize(self):
        """Initialize migration system."""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        async with aiosqlite.connect(self.db_path) as db:
            # Create schema version table if not exists
            await db.execute("""
                CREATE TABLE IF NOT EXISTS schema_version (
                    version INTEGER PRIMARY KEY,
                    applied_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    name TEXT
                )
            """)
            await db.commit()
    
    async def get_current_version(self) -> int:
        """Get current database schema version."""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT MAX(version) FROM schema_version"
            ) as cursor:
                row = await cursor.fetchone()
                return row[0] if row and row[0] else 0
    
    async def migrate(self, target_version: Optional[int] = None) -> List[str]:
        """Run pending migrations.
        
        Args:
            target_version: Target version to migrate to (None = latest)
            
        Returns:
            List of migration names that were applied
        """
        await self.initialize()
        current_version = await self.get_current_version()
        
        if target_version is None:
            target_version = max(m.version for m in self.migrations)
        
        applied = []
        
        async with aiosqlite.connect(self.db_path) as db:
            for migration in self.migrations:
                if current_version < migration.version <= target_version:
                    logger.info(f"Applying migration {migration.version}: {migration.name}")
                    
                    # Execute migration
                    await db.executescript(migration.up_sql)
                    
                    # Record migration
                    await db.execute(
                        "INSERT INTO schema_version (version, name) VALUES (?, ?)",
                        (migration.version, migration.name)
                    )
                    
                    await db.commit()
                    applied.append(migration.name)
                    logger.info(f"Migration {migration.version} applied successfully")
        
        return applied
    
    async def rollback(self, target_version: int) -> List[str]:
        """Rollback to a specific version.
        
        Args:
            target_version: Version to rollback to
            
        Returns:
            List of migration names that were rolled back
        """
        current_version = await self.get_current_version()
        rolled_back = []
        
        if target_version >= current_version:
            logger.warning("Target version is >= current version, nothing to rollback")
            return rolled_back
        
        async with aiosqlite.connect(self.db_path) as db:
            for migration in reversed(self.migrations):
                if migration.version > target_version and migration.down_sql:
                    logger.info(f"Rolling back migration {migration.version}: {migration.name}")
                    
                    await db.executescript(migration.down_sql)
                    await db.execute(
                        "DELETE FROM schema_version WHERE version = ?",
                        (migration.version,)
                    )
                    
                    await db.commit()
                    rolled_back.append(migration.name)
        
        return rolled_back
    
    async def status(self) -> dict:
        """Get migration status."""
        await self.initialize()
        current = await self.get_current_version()
        latest = max(m.version for m in self.migrations)
        
        pending = [m.name for m in self.migrations if m.version > current]
        
        return {
            'current_version': current,
            'latest_version': latest,
            'pending_migrations': pending,
            'is_up_to_date': current == latest
        }
