"""Test configuration and fixtures."""
import pytest
import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from src.models.product import Product, StockAlert, AlertType, TrackedProduct


@pytest.fixture
def event_loop():
    """Create an instance of the default event loop for each test case."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def sample_product():
    """Create a sample product for testing."""
    return Product(
        id="test_123",
        name="Pokemon Paldean Fates Booster Box",
        retailer="EB Games",
        url="https://www.ebgames.com.au/product/pokemon-paldean-fates",
        price=199.99,
        in_stock=True,
        category="pokemon",
        set_name="Paldean Fates",
        last_checked=datetime.now(),
        last_in_stock=datetime.now()
    )


@pytest.fixture
def sample_alert(sample_product):
    """Create a sample stock alert for testing."""
    return StockAlert(
        product=sample_product,
        alert_type=AlertType.IN_STOCK,
        timestamp=datetime.now(),
        previous_status=False,
        message="Back in stock!"
    )


@pytest.fixture
def mock_database():
    """Create a mock database for testing."""
    db = MagicMock()
    db.connect = AsyncMock()
    db.close = AsyncMock()
    db.get_product = AsyncMock(return_value=None)
    db.save_product = AsyncMock()
    db.get_all_products = AsyncMock(return_value=[])
    db.should_send_alert = AsyncMock(return_value=True)
    db.save_alert = AsyncMock(return_value=1)
    db.mark_alert_sent = AsyncMock()
    return db


@pytest.fixture
def mock_discord_channel():
    """Create a mock Discord channel for testing."""
    channel = AsyncMock()
    channel.send = AsyncMock()
    return channel


@pytest.fixture
def sample_html_eb_games():
    """Sample EB Games HTML for testing scrapers."""
    return """
    <html>
    <body>
        <div class="product-item">
            <a href="/product/pokemon-box" class="product-link">
                <h3 class="product-title">Pokemon Paldean Fates Booster Box</h3>
            </a>
            <span class="price">$199.99</span>
            <div class="stock-status">In Stock</div>
            <button class="add-to-cart">Add to Cart</button>
            <img src="https://example.com/image.jpg" />
        </div>
    </body>
    </html>
    """


@pytest.fixture
def sample_html_jb_hifi():
    """Sample JB Hi-Fi HTML for testing scrapers."""
    return """
    <html>
    <body>
        <div class="product-tile">
            <a href="/products/one-piece-box" class="product-tile-link">
                <h3 class="product-tile-title">One Piece Romance Dawn Booster Box</h3>
            </a>
            <span class="price">$179.99</span>
            <div class="availability">Available Online</div>
            <button class="add-to-cart">Add to Cart</button>
            <img class="product-image" src="https://example.com/op-image.jpg" />
        </div>
    </body>
    </html>
    """
