"""Data models for Zack Vision."""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List
from enum import Enum


class AlertType(Enum):
    """Types of stock alerts."""
    IN_STOCK = 'in_stock'
    OUT_OF_STOCK = 'out_of_stock'
    PRICE_CHANGE = 'price_change'
    NEW_PRODUCT = 'new_product'


class ProductCategory(Enum):
    """Product categories."""
    POKEMON = 'pokemon'
    ONE_PIECE = 'one_piece'
    UNKNOWN = 'unknown'


@dataclass
class Product:
    """Represents a TCG product."""
    id: str
    name: str
    retailer: str
    url: str
    price: Optional[float] = None
    currency: str = 'AUD'
    in_stock: bool = False
    image_url: Optional[str] = None
    category: str = ''  # 'pokemon', 'one_piece', 'unknown'
    set_name: Optional[str] = None
    pack_type: str = 'box'  # Always 'box' since we only track booster boxes
    last_checked: Optional[datetime] = None
    last_in_stock: Optional[datetime] = None
    created_at: Optional[datetime] = field(default_factory=datetime.now)
    
    def __hash__(self):
        return hash(self.id)
    
    def __eq__(self, other):
        if not isinstance(other, Product):
            return False
        return self.id == other.id
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            'id': self.id,
            'name': self.name,
            'retailer': self.retailer,
            'url': self.url,
            'price': self.price,
            'currency': self.currency,
            'in_stock': self.in_stock,
            'image_url': self.image_url,
            'category': self.category,
            'set_name': self.set_name,
            'pack_type': self.pack_type,
            'last_checked': self.last_checked.isoformat() if self.last_checked else None,
            'last_in_stock': self.last_in_stock.isoformat() if self.last_in_stock else None,
        }


@dataclass
class StockAlert:
    """Represents a stock alert."""
    product: Product
    alert_type: AlertType
    timestamp: datetime
    previous_status: Optional[bool] = None
    previous_price: Optional[float] = None
    message: Optional[str] = None
    sent: bool = False
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            'product': self.product.to_dict(),
            'alert_type': self.alert_type.value,
            'timestamp': self.timestamp.isoformat(),
            'previous_status': self.previous_status,
            'previous_price': self.previous_price,
            'message': self.message,
            'sent': self.sent,
        }


@dataclass
class TrackedProduct:
    """Represents a user-tracked product."""
    id: str
    url: str
    name: Optional[str] = None
    added_by: Optional[int] = None  # Discord user ID
    added_at: Optional[datetime] = field(default_factory=datetime.now)
    enabled: bool = True
    alert_channel_id: Optional[int] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            'id': self.id,
            'url': self.url,
            'name': self.name,
            'added_by': self.added_by,
            'added_at': self.added_at.isoformat() if self.added_at else None,
            'enabled': self.enabled,
            'alert_channel_id': self.alert_channel_id,
        }


@dataclass
class StockHistory:
    """Represents a stock history entry."""
    id: Optional[int] = None
    product_id: str = ''
    in_stock: bool = False
    price: Optional[float] = None
    timestamp: Optional[datetime] = field(default_factory=datetime.now)
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            'id': self.id,
            'product_id': self.product_id,
            'in_stock': self.in_stock,
            'price': self.price,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
        }


@dataclass
class UserPreference:
    """Represents a user's notification preferences."""
    user_id: int
    alerts_enabled: bool = True
    alert_types: List[str] = field(default_factory=lambda: ['in_stock'])
    created_at: Optional[datetime] = field(default_factory=datetime.now)
    updated_at: Optional[datetime] = field(default_factory=datetime.now)
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            'user_id': self.user_id,
            'alerts_enabled': self.alerts_enabled,
            'alert_types': self.alert_types,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
