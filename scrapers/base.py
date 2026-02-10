import hashlib
import random
import asyncio
import logging
from abc import ABC, abstractmethod
from typing import List, Optional
from models import Product
from config import USER_AGENTS, REQUEST_DELAY_MIN, REQUEST_DELAY_MAX, RETRY_ATTEMPTS, RETRY_DELAY_BASE
import aiohttp
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

class BaseScraper(ABC):
    """Base class for all retail scrapers"""
    
    def __init__(self, retailer_name: str, base_url: str):
        self.retailer_name = retailer_name
        self.base_url = base_url
        self.session = None
        self._last_request_time = None
    
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
    
    def _is_tcgp_product(self, name: str) -> bool:
        """Check if product is a booster box ONLY (no packs)"""
        name_lower = name.lower()
        
        # ONLY include booster boxes - explicitly exclude packs
        box_keywords = [
            'booster box', 'booster display', 'display box', 
            'case', 'carton', '36 pack', '24 pack', 'booster case',
        ]
        
        # Exclude booster packs and non-TCG items
        exclude_keywords = [
            'booster pack', 'blister', '3-pack', '6-pack', '10-pack', 
            'single pack', 'booster sleeve', 'sleeve', 'binder', 
            'playmat', 'deck box', 'card sleeves', 'elite trainer box'
        ]
        
        # First check if it's excluded (packs)
        if any(keyword in name_lower for keyword in exclude_keywords):
            return False
        
        # Then check if it's a box
        return any(keyword in name_lower for keyword in box_keywords)
    
    def _get_product_type(self, name: str) -> str:
        """Determine product type - always returns 'box' since we only track boxes"""
        return 'box'
    
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
    
    async def _apply_rate_limit(self):
        """Apply rate limiting delay between requests"""
        if self._last_request_time is not None:
            elapsed = asyncio.get_event_loop().time() - self._last_request_time
            delay = random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX)
            if elapsed < delay:
                await asyncio.sleep(delay - elapsed)
        self._last_request_time = asyncio.get_event_loop().time()
    
    async def _make_request(self, url: str, method: str = 'GET', **kwargs) -> Optional[aiohttp.ClientResponse]:
        """Make HTTP request with retry logic and rate limiting"""
        await self._apply_rate_limit()
        
        for attempt in range(RETRY_ATTEMPTS):
            try:
                logger.debug(f"{self.retailer_name}: {method} {url} (attempt {attempt + 1}/{RETRY_ATTEMPTS})")
                
                if method.upper() == 'GET':
                    async with self.session.get(url, timeout=30, **kwargs) as response:
                        if response.status == 200:
                            return response
                        elif response.status == 429:  # Rate limited
                            retry_after = int(response.headers.get('Retry-After', RETRY_DELAY_BASE * (2 ** attempt)))
                            logger.warning(f"{self.retailer_name}: Rate limited, waiting {retry_after}s")
                            await asyncio.sleep(retry_after)
                        else:
                            logger.warning(f"{self.retailer_name}: HTTP {response.status} for {url}")
                            
            except asyncio.TimeoutError:
                logger.warning(f"{self.retailer_name}: Timeout on attempt {attempt + 1}")
            except Exception as e:
                logger.error(f"{self.retailer_name}: Request error on attempt {attempt + 1}: {e}")
            
            if attempt < RETRY_ATTEMPTS - 1:
                backoff = RETRY_DELAY_BASE * (2 ** attempt) + random.uniform(0, 1)
                logger.info(f"{self.retailer_name}: Retrying in {backoff:.1f}s...")
                await asyncio.sleep(backoff)
        
        logger.error(f"{self.retailer_name}: All {RETRY_ATTEMPTS} attempts failed for {url}")
        return None
    
    async def __aenter__(self):
        """Async context manager entry"""
        self.session = aiohttp.ClientSession(headers=self._get_headers())
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()
