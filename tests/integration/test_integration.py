"""Integration tests for the complete system."""
import pytest
import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from src.services.database import Database
from src.services.scheduler import StockScheduler
from src.services.dead_letter_queue import DeadLetterQueue
from src.models.product import Product, StockAlert, AlertType


@pytest.mark.integration
class TestDatabaseIntegration:
    """Integration tests for database operations."""
    
    @pytest.fixture
    async def db(self, tmp_path):
        """Create a test database."""
        db_path = tmp_path / "test.db"
        database = Database(str(db_path))
        await database.connect()
        yield database
        await database.close()
    
    async def test_save_and_retrieve_product(self, db):
        """Test saving and retrieving a product."""
        product = Product(
            id="test_123",
            name="Test Pokemon Box",
            retailer="Test Store",
            url="https://test.com/product",
            price=199.99,
            in_stock=True,
            category="pokemon",
            set_name="Test Set"
        )
        
        # Save product
        await db.save_product(product)
        
        # Retrieve product
        retrieved = await db.get_product("test_123")
        
        assert retrieved is not None
        assert retrieved.id == product.id
        assert retrieved.name == product.name
        assert retrieved.price == product.price
        assert retrieved.in_stock == product.in_stock
    
    async def test_stock_history_tracking(self, db):
        """Test stock history is tracked correctly."""
        product = Product(
            id="test_456",
            name="Test Box",
            retailer="Store",
            url="http://test.com",
            in_stock=False
        )
        
        # Save initial state
        await db.save_product(product)
        await db.save_stock_history(product)
        
        # Update and save again
        product.in_stock = True
        await db.save_product(product)
        await db.save_stock_history(product)
        
        # Check we can get in stock products
        in_stock = await db.get_in_stock_products()
        assert len(in_stock) == 1
        assert in_stock[0].id == "test_456"
    
    async def test_pagination(self, db):
        """Test database pagination."""
        # Create 150 products
        for i in range(150):
            product = Product(
                id=f"test_{i}",
                name=f"Product {i}",
                retailer="Store",
                url=f"http://test.com/{i}"
            )
            await db.save_product(product)
        
        # Test pagination
        page1 = await db.get_all_products(limit=50, offset=0)
        page2 = await db.get_all_products(limit=50, offset=50)
        page3 = await db.get_all_products(limit=50, offset=100)
        
        assert len(page1) == 50
        assert len(page2) == 50
        assert len(page3) == 50
        assert page1[0].id != page2[0].id
    
    async def test_alert_cooldown(self, db):
        """Test alert cooldown mechanism."""
        # First alert should be allowed
        should_send = await db.should_send_alert("product_1", cooldown_seconds=300)
        assert should_send is True
        
        # Save an alert
        product = Product(id="product_1", name="Test", retailer="Store", url="http://test")
        alert = StockAlert(
            product=product,
            alert_type=AlertType.IN_STOCK,
            timestamp=datetime.now()
        )
        await db.save_alert(alert)
        
        # Second alert should be blocked (cooldown active)
        should_send = await db.should_send_alert("product_1", cooldown_seconds=300)
        assert should_send is False


@pytest.mark.integration
class TestSchedulerIntegration:
    """Integration tests for scheduler."""
    
    @pytest.fixture
    async def scheduler_setup(self, tmp_path):
        """Setup scheduler with mock components."""
        db = Database(str(tmp_path / "test.db"))
        await db.connect()
        
        mock_bot = MagicMock()
        alert_callback = AsyncMock()
        
        scheduler = StockScheduler(mock_bot, db, alert_callback)
        
        yield scheduler, db, alert_callback
        
        await scheduler.stop()
        await db.close()
    
    async def test_scheduler_stats(self, scheduler_setup):
        """Test scheduler statistics tracking."""
        scheduler, db, _ = scheduler_setup
        
        # Check initial stats
        status = scheduler.get_status()
        assert status['running'] is False
        assert status['stats']['total_checks'] == 0
        
        # Simulate some activity
        scheduler._stats.total_checks = 10
        scheduler._stats.successful_checks = 9
        scheduler._stats.failed_checks = 1
        
        status = scheduler.get_status()
        assert status['stats']['total_checks'] == 10
        assert status['stats']['successful_checks'] == 9
        assert status['stats']['failed_checks'] == 1


@pytest.mark.integration
class TestDeadLetterQueueIntegration:
    """Integration tests for dead letter queue."""
    
    @pytest.fixture
    async def dlq_setup(self, tmp_path):
        """Setup DLQ with database."""
        db = Database(str(tmp_path / "test.db"))
        await db.connect()
        
        # Run migrations to create DLQ table
        from src.services.migrations import MigrationManager
        migrator = MigrationManager(str(tmp_path / "test.db"))
        await migrator.migrate()
        
        dlq = DeadLetterQueue(db, max_retries=3, retry_delay_minutes=0)
        
        yield dlq, db
        
        await db.close()
    
    async def test_failed_alert_lifecycle(self, dlq_setup):
        """Test complete lifecycle of a failed alert."""
        dlq, db = dlq_setup
        
        # Create a failed alert
        product = Product(id="test_789", name="Test", retailer="Store", url="http://test")
        alert = StockAlert(product=product, alert_type=AlertType.IN_STOCK, timestamp=datetime.now())
        
        # Add to DLQ
        failed_id = await dlq.add_failed_alert(alert, "Discord API error")
        assert failed_id is not None
        
        # Check stats
        stats = await dlq.get_stats()
        assert stats['pending'] == 1
        assert stats['resolved'] == 0
        
        # Increment retry
        await dlq.increment_retry(failed_id)
        
        # Mark as resolved
        await dlq.mark_resolved(failed_id)
        
        # Check updated stats
        stats = await dlq.get_stats()
        assert stats['pending'] == 0
        assert stats['resolved'] == 1


@pytest.mark.integration
class TestEndToEnd:
    """End-to-end integration tests."""
    
    @pytest.mark.asyncio
    async def test_complete_alert_flow(self, tmp_path):
        """Test complete flow from product discovery to alert."""
        # This test simulates the entire flow
        db = Database(str(tmp_path / "e2e.db"))
        await db.connect()
        
        try:
            # 1. Product discovered
            product = Product(
                id="e2e_001",
                name="E2E Test Box",
                retailer="Test Store",
                url="http://e2e.test/product",
                price=150.00,
                in_stock=False  # Initially out of stock
            )
            
            # 2. Save product
            await db.save_product(product)
            await db.save_stock_history(product)
            
            # 3. Product comes in stock
            product.in_stock = True
            product.last_in_stock = datetime.now()
            
            # 4. Check if we should alert (first time - yes)
            should_alert = await db.should_send_alert(product.id, cooldown_seconds=300)
            assert should_alert is True
            
            # 5. Create and save alert
            alert = StockAlert(
                product=product,
                alert_type=AlertType.IN_STOCK,
                timestamp=datetime.now(),
                previous_status=False
            )
            alert_id = await db.save_alert(alert)
            await db.mark_alert_sent(alert_id)
            
            # 6. Save updated product
            await db.save_product(product)
            await db.save_stock_history(product)
            
            # 7. Verify alert was saved
            recent_alerts = await db.get_recent_alerts(hours=1)
            assert len(recent_alerts) == 1
            assert recent_alerts[0]['product_id'] == "e2e_001"
            
            # 8. Verify product is marked in stock
            in_stock_products = await db.get_in_stock_products()
            assert len(in_stock_products) == 1
            
            # 9. Second alert should be blocked by cooldown
            should_alert = await db.should_send_alert(product.id, cooldown_seconds=300)
            assert should_alert is False
            
        finally:
            await db.close()
