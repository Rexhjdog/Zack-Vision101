"""Core domain models."""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime, timezone


class AlertType(enum.Enum):
    IN_STOCK = "in_stock"
    OUT_OF_STOCK = "out_of_stock"
    PRICE_CHANGE = "price_change"
    NEW_PRODUCT = "new_product"


@dataclass
class Product:
    """A TCG product listed by a retailer."""

    name: str
    url: str
    retailer: str
    in_stock: bool = False
    price: float | None = None
    category: str = "unknown"  # "pokemon" | "one_piece" | "unknown"
    set_name: str = ""
    image_url: str = ""
    last_checked: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def display_price(self) -> str:
        if self.price is None:
            return "N/A"
        return f"${self.price:.2f}"


@dataclass
class StockAlert:
    """Represents a stock-change event to report."""

    product: Product
    alert_type: AlertType
    previous_price: float | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def is_restock(self) -> bool:
        return self.alert_type == AlertType.IN_STOCK


@dataclass
class TrackedProduct:
    """A product URL added by a user for monitoring."""

    url: str
    name: str = ""
    added_by: int = 0  # Discord user id
    retailer: str = ""
    added_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class StockHistory:
    """One row in the stock-history table."""

    product_url: str
    retailer: str
    in_stock: bool
    price: float | None
    recorded_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
