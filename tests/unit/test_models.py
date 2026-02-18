"""Tests for data models."""

from src.models.product import AlertType, Product, StockAlert


class TestProduct:
    def test_display_price_with_value(self):
        p = Product(name="Test", url="https://x.com", retailer="R", price=59.99)
        assert p.display_price == "$59.99"

    def test_display_price_none(self):
        p = Product(name="Test", url="https://x.com", retailer="R", price=None)
        assert p.display_price == "N/A"

    def test_default_category(self):
        p = Product(name="Test", url="https://x.com", retailer="R")
        assert p.category == "unknown"

    def test_default_not_in_stock(self):
        p = Product(name="Test", url="https://x.com", retailer="R")
        assert p.in_stock is False


class TestStockAlert:
    def test_is_restock_true(self):
        p = Product(name="X", url="https://x.com", retailer="R", in_stock=True)
        alert = StockAlert(product=p, alert_type=AlertType.IN_STOCK)
        assert alert.is_restock is True

    def test_is_restock_false_for_price_change(self):
        p = Product(name="X", url="https://x.com", retailer="R", in_stock=True)
        alert = StockAlert(product=p, alert_type=AlertType.PRICE_CHANGE)
        assert alert.is_restock is False
