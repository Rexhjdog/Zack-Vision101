"""Unit tests for data models."""
import pytest
from datetime import datetime
from src.models.product import Product, StockAlert, TrackedProduct, AlertType, ProductCategory


class TestProduct:
    """Test Product model."""
    
    def test_product_creation(self):
        """Test creating a Product instance."""
        product = Product(
            id="test_123",
            name="Pokemon Booster Box",
            retailer="EB Games",
            url="https://example.com/product",
            price=199.99,
            in_stock=True
        )
        
        assert product.id == "test_123"
        assert product.name == "Pokemon Booster Box"
        assert product.retailer == "EB Games"
        assert product.price == 199.99
        assert product.in_stock is True
        assert product.currency == "AUD"  # Default value
        assert product.pack_type == "box"  # Default value
    
    def test_product_equality(self):
        """Test Product equality based on ID."""
        product1 = Product(id="same_id", name="Box 1", retailer="Store", url="http://test")
        product2 = Product(id="same_id", name="Box 2", retailer="Other", url="http://other")
        product3 = Product(id="different_id", name="Box 1", retailer="Store", url="http://test")
        
        assert product1 == product2  # Same ID
        assert product1 != product3  # Different ID
        assert hash(product1) == hash(product2)
    
    def test_product_to_dict(self):
        """Test Product serialization to dict."""
        now = datetime.now()
        product = Product(
            id="test_123",
            name="Pokemon Box",
            retailer="EB Games",
            url="https://example.com",
            price=199.99,
            in_stock=True,
            last_checked=now,
            category="pokemon"
        )
        
        data = product.to_dict()
        
        assert data["id"] == "test_123"
        assert data["name"] == "Pokemon Box"
        assert data["price"] == 199.99
        assert data["in_stock"] is True
        assert data["last_checked"] == now.isoformat()
    
    def test_product_default_values(self):
        """Test Product default values."""
        product = Product(
            id="test",
            name="Test Box",
            retailer="Test Store",
            url="http://test.com"
        )
        
        assert product.price is None
        assert product.in_stock is False
        assert product.category == ""
        assert product.set_name is None


class TestStockAlert:
    """Test StockAlert model."""
    
    def test_alert_creation(self):
        """Test creating a StockAlert instance."""
        product = Product(id="test", name="Box", retailer="Store", url="http://test")
        alert = StockAlert(
            product=product,
            alert_type=AlertType.IN_STOCK,
            timestamp=datetime.now(),
            previous_status=False
        )
        
        assert alert.product == product
        assert alert.alert_type == AlertType.IN_STOCK
        assert alert.previous_status is False
        assert alert.sent is False  # Default
    
    def test_alert_to_dict(self):
        """Test StockAlert serialization."""
        product = Product(id="test", name="Box", retailer="Store", url="http://test")
        now = datetime.now()
        alert = StockAlert(
            product=product,
            alert_type=AlertType.PRICE_CHANGE,
            timestamp=now,
            previous_price=199.99,
            message="Price dropped!"
        )
        
        data = alert.to_dict()
        
        assert data["alert_type"] == "price_change"
        assert data["previous_price"] == 199.99
        assert data["message"] == "Price dropped!"
        assert data["product"]["id"] == "test"


class TestTrackedProduct:
    """Test TrackedProduct model."""
    
    def test_tracked_product_creation(self):
        """Test creating a TrackedProduct instance."""
        tracked = TrackedProduct(
            id="user_123",
            url="https://example.com/product",
            name="Pokemon Box",
            added_by=123456789,
            alert_channel_id=987654321
        )
        
        assert tracked.id == "user_123"
        assert tracked.url == "https://example.com/product"
        assert tracked.name == "Pokemon Box"
        assert tracked.added_by == 123456789
        assert tracked.enabled is True  # Default
    
    def test_tracked_product_to_dict(self):
        """Test TrackedProduct serialization."""
        now = datetime.now()
        tracked = TrackedProduct(
            id="user_123",
            url="https://example.com",
            name="Test",
            added_by=123,
            added_at=now
        )
        
        data = tracked.to_dict()
        
        assert data["id"] == "user_123"
        assert data["added_by"] == 123
        assert data["added_at"] == now.isoformat()
        assert data["enabled"] is True


class TestAlertType:
    """Test AlertType enum."""
    
    def test_alert_type_values(self):
        """Test AlertType enum values."""
        assert AlertType.IN_STOCK.value == "in_stock"
        assert AlertType.OUT_OF_STOCK.value == "out_of_stock"
        assert AlertType.PRICE_CHANGE.value == "price_change"
        assert AlertType.NEW_PRODUCT.value == "new_product"


class TestProductCategory:
    """Test ProductCategory enum."""
    
    def test_product_category_values(self):
        """Test ProductCategory enum values."""
        assert ProductCategory.POKEMON.value == "pokemon"
        assert ProductCategory.ONE_PIECE.value == "one_piece"
        assert ProductCategory.UNKNOWN.value == "unknown"
