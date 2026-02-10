from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List

@dataclass
class Product:
    """Represents a TCG product"""
    id: str
    name: str
    retailer: str
    url: str
    price: Optional[float] = None
    currency: str = 'AUD'
    in_stock: bool = False
    image_url: Optional[str] = None
    category: str = ''  # 'pokemon' or 'one_piece'
    set_name: Optional[str] = None
    pack_type: str = ''  # 'booster', 'blister', 'etb', etc.
    last_checked: Optional[datetime] = None
    last_in_stock: Optional[datetime] = None
    
    def __hash__(self):
        return hash(self.id)
    
    def __eq__(self, other):
        if not isinstance(other, Product):
            return False
        return self.id == other.id

@dataclass
class StockAlert:
    """Represents a stock alert"""
    product: Product
    alert_type: str  # 'in_stock', 'out_of_stock', 'price_change'
    timestamp: datetime
    previous_status: Optional[bool] = None
    previous_price: Optional[float] = None
    message: Optional[str] = None

@dataclass
class TrackedProduct:
    """Represents a user-tracked product"""
    id: str
    url: str
    name: Optional[str] = None
    added_by: Optional[int] = None  # Discord user ID
    added_at: Optional[datetime] = None
    enabled: bool = True
    alert_channel_id: Optional[int] = None
