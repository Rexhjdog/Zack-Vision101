"""Shared test fixtures."""

from __future__ import annotations

import asyncio
import os
import tempfile

import pytest
import pytest_asyncio

# Ensure config uses harmless defaults during tests
os.environ.setdefault("DISCORD_TOKEN", "test-token")
os.environ.setdefault("DISCORD_CHANNEL_ID", "123456789")

from src.models.product import AlertType, Product, StockAlert
from src.services.database import Database


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def db(tmp_path):
    """Provide a fresh database for each test."""
    db_path = str(tmp_path / "test.db")
    database = Database(db_path)
    await database.connect()
    yield database
    await database.close()


@pytest.fixture
def sample_product() -> Product:
    return Product(
        name="Pokemon TCG Paldean Fates Booster Box",
        url="https://www.ebgames.com.au/product/trading-cards/123",
        retailer="EB Games",
        in_stock=True,
        price=89.99,
        category="pokemon",
        set_name="Paldean Fates",
    )


@pytest.fixture
def sample_alert(sample_product) -> StockAlert:
    return StockAlert(
        product=sample_product,
        alert_type=AlertType.IN_STOCK,
    )
