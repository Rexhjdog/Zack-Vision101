import hashlib
import random
from abc import ABC, abstractmethod
from typing import List, Optional
from models import Product
from config import USER_AGENTS
import aiohttp
from bs4 import BeautifulSoup

class BaseScraper(ABC):
    """Base class for all retail scrapers"""
    
    def __init__(self, retailer_name: str, base_url: str):
        self.retailer_name = retailer_name
        self.base_url = base_url
        self.session = None
    
    def _generate_product_id(self, url: str) -> str:
        """Generate unique product ID from URL"""
        return hashlib.md5(f"{self.retailer_name}:{url}".encode()).hexdigest()[:16]
    
    def _get_headers(self) -> dict:
        """Get randomized headers"""
        return {
            'User-Agent': random.choice(USER_AGENTS),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
    
    @abstractmethod
    async def search_products(self, query: str) -> List[Product]:
        """Search for products"""
        pass
    
    @abstractmethod
    async def get_product_details(self, url: str) -> Optional[Product]:
        """Get detailed product info"""
        pass
    
    def _extract_price(self, price_text: str) -> Optional[float]:
        """Extract price from text"""
        if not price_text:
            return None
        
        # Remove currency symbols and whitespace
        price_text = price_text.replace('$', '').replace('AUD', '').replace(',', '').strip()
        
        try:
            return float(price_text)
        except ValueError:
            return None
    
    def _is_booster_pack(self, name: str) -> bool:
        """Check if product is a booster pack"""
        name_lower = name.lower()
        booster_keywords = [
            'booster pack', 'booster', 'pack', 'blister', 
            '3-pack', '6-pack', '10-pack', 'collector'
        ]
        
        # Exclude booster boxes
        box_keywords = ['booster box', 'display box', 'case', 'carton']
        if any(keyword in name_lower for keyword in box_keywords):
            return False
        
        return any(keyword in name_lower for keyword in booster_keywords)
    
    def _categorize_product(self, name: str) -> str:
        """Categorize as pokemon or one_piece"""
        name_lower = name.lower()
        
        if 'pokemon' in name_lower or 'pokémon' in name_lower:
            return 'pokemon'
        elif 'one piece' in name_lower:
            return 'one_piece'
        
        return 'unknown'
    
    def _extract_set_name(self, name: str) -> Optional[str]:
        """Extract TCG set name from product name"""
        from config import POKEMON_SETS, ONE_PIECE_SETS
        
        name_lower = name.lower()
        
        for set_name in POKEMON_SETS:
            if set_name.lower() in name_lower:
                return set_name
        
        for set_name in ONE_PIECE_SETS:
            if set_name.lower() in name_lower:
                return set_name
        
        return None
    
    async def __aenter__(self):
        """Async context manager entry"""
        self.session = aiohttp.ClientSession(headers=self._get_headers())
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()
