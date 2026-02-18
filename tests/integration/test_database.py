"""Integration tests for async database operations."""

from __future__ import annotations

import pytest

from src.models.product import AlertType, Product, StockAlert, TrackedProduct
from src.services.database import Database


@pytest.mark.asyncio
class TestDatabaseProducts:
    async def test_upsert_and_get(self, db: Database, sample_product: Product):
        await db.upsert_product(sample_product)
        fetched = await db.get_product(sample_product.url)
        assert fetched is not None
        assert fetched.name == sample_product.name
        assert fetched.in_stock == sample_product.in_stock
        assert fetched.price == sample_product.price

    async def test_get_nonexistent(self, db: Database):
        result = await db.get_product("https://example.com/nope")
        assert result is None

    async def test_upsert_updates_existing(self, db: Database, sample_product: Product):
        await db.upsert_product(sample_product)
        sample_product.price = 79.99
        sample_product.in_stock = False
        await db.upsert_product(sample_product)

        fetched = await db.get_product(sample_product.url)
        assert fetched is not None
        assert fetched.price == 79.99
        assert fetched.in_stock is False

    async def test_count(self, db: Database, sample_product: Product):
        await db.upsert_product(sample_product)
        assert await db.get_total_product_count() == 1
        assert await db.get_in_stock_count() == 1

    async def test_get_by_retailer(self, db: Database, sample_product: Product):
        await db.upsert_product(sample_product)
        products = await db.get_products_by_retailer("EB Games")
        assert len(products) == 1


@pytest.mark.asyncio
class TestDatabaseAlerts:
    async def test_record_and_count(self, db: Database, sample_alert: StockAlert):
        await db.upsert_product(sample_alert.product)
        await db.record_alert(sample_alert)
        count = await db.get_recent_alert_count(24)
        assert count == 1

    async def test_recently_alerted(self, db: Database, sample_alert: StockAlert):
        await db.upsert_product(sample_alert.product)
        await db.record_alert(sample_alert)
        assert await db.was_recently_alerted(sample_alert.product.url, 300) is True
        assert await db.was_recently_alerted("https://other.com", 300) is False


@pytest.mark.asyncio
class TestDatabaseTracked:
    async def test_add_and_list(self, db: Database):
        tp = TrackedProduct(
            url="https://www.ebgames.com.au/product/123",
            name="Test Product",
            added_by=999,
            retailer="EB Games",
        )
        await db.add_tracked(tp)
        all_tracked = await db.get_all_tracked()
        assert len(all_tracked) == 1
        assert all_tracked[0].url == tp.url

    async def test_remove(self, db: Database):
        tp = TrackedProduct(
            url="https://www.ebgames.com.au/product/456",
            name="Remove Me",
            retailer="EB Games",
        )
        await db.add_tracked(tp)
        removed = await db.remove_tracked(tp.url)
        assert removed is True
        assert await db.get_all_tracked() == []

    async def test_remove_nonexistent(self, db: Database):
        removed = await db.remove_tracked("https://nope.com")
        assert removed is False


@pytest.mark.asyncio
class TestDatabaseHistory:
    async def test_record_history(self, db: Database, sample_product: Product):
        await db.record_history(sample_product)
        # No error means success; we can verify via cleanup
        deleted = await db.cleanup_old_history()
        assert deleted == 0  # Just added, so nothing old to clean
