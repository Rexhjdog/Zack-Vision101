"""Base scraper class with circuit breaker, rate limiting, and retry logic."""
import asyncio
import hashlib
import random
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from enum import Enum

import aiohttp
from bs4 import BeautifulSoup

from src.config import (
    USER_AGENTS, REQUEST_DELAY_MIN, REQUEST_DELAY_MAX,
    RETRY_ATTEMPTS, RETRY_DELAY_BASE, REQUEST_TIMEOUT,
    BOOSTER_BOX_KEYWORDS, EXCLUDE_KEYWORDS, POKEMON_SETS, ONE_PIECE_SETS
)
from src.models.product import Product

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = 'closed'      # Normal operation
    OPEN = 'open'          # Failing, rejecting requests
    HALF_OPEN = 'half_open'  # Testing if recovered


@dataclass
class CircuitBreaker:
    """Circuit breaker for handling cascading failures."""
    failure_threshold: int = 5
    recovery_timeout: int = 60  # seconds
    
    def __post_init__(self):
        self.failures = 0
        self.last_failure_time: Optional[datetime] = None
        self.state = CircuitState.CLOSED
    
    def record_success(self):
        """Record a successful request."""
        self.failures = 0
        self.state = CircuitState.CLOSED
    
    def record_failure(self) -> bool:
        """Record a failed request. Returns True if circuit is now open."""
        self.failures += 1
        self.last_failure_time = datetime.now()
        
        if self.failures >= self.failure_threshold:
            self.state = CircuitState.OPEN
            logger.warning(f"Circuit breaker opened after {self.failures} failures")
            return True
        return False
    
    def can_execute(self) -> bool:
        """Check if request can be executed."""
        if self.state == CircuitState.CLOSED:
            return True
        
        if self.state == CircuitState.OPEN:
            if self.last_failure_time:
                elapsed = (datetime.now() - self.last_failure_time).total_seconds()
                if elapsed >= self.recovery_timeout:
                    self.state = CircuitState.HALF_OPEN
                    logger.info("Circuit breaker entering half-open state")
                    return True
            return False
        
        return True  # HALF_OPEN


class BaseScraper(ABC):
    """Base scraper with circuit breaker, rate limiting, and retry logic."""
    
    def __init__(self, retailer_name: str, base_url: str):
        self.retailer_name = retailer_name
        self.base_url = base_url
        self.session: Optional[aiohttp.ClientSession] = None
        self._last_request_time: Optional[float] = None
        self._circuit_breaker = CircuitBreaker()
        self._headers = self._get_headers()
    
    def _get_headers(self) -> Dict[str, str]:
        """Get randomized request headers."""
        return {
            'User-Agent': random.choice(USER_AGENTS),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9,en-AU;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Cache-Control': 'max-age=0',
        }
    
    def _generate_product_id(self, url: str) -> str:
        """Generate unique product ID from URL."""
        return hashlib.md5(f"{self.retailer_name}:{url}".encode()).hexdigest()[:16]
    
    def _extract_price(self, price_text: Optional[str]) -> Optional[float]:
        """Extract price from text."""
        if not price_text:
            return None
        
        # Remove currency symbols and whitespace
        cleaned = price_text.replace('$', '').replace('AUD', '').replace(',', '').strip()
        
        # Extract first number found
        import re
        match = re.search(r'\d+\.?\d*', cleaned)
        if match:
            try:
                return float(match.group())
            except ValueError:
                pass
        return None
    
    def _is_booster_box(self, name: str) -> bool:
        """Check if product is a booster box (not pack)."""
        name_lower = name.lower()
        
        # Check exclusion keywords first
        for keyword in EXCLUDE_KEYWORDS:
            if keyword in name_lower:
                return False
        
        # Check for booster box keywords
        for keyword in BOOSTER_BOX_KEYWORDS:
            if keyword in name_lower:
                return True
        
        return False
    
    def _categorize_product(self, name: str) -> str:
        """Categorize as pokemon or one_piece."""
        name_lower = name.lower()
        
        if 'pokemon' in name_lower or 'pokémon' in name_lower:
            return 'pokemon'
        elif 'one piece' in name_lower:
            return 'one_piece'
        
        return 'unknown'
    
    def _extract_set_name(self, name: str) -> Optional[str]:
        """Extract TCG set name from product name."""
        name_lower = name.lower()
        
        for set_name in POKEMON_SETS:
            if set_name.lower() in name_lower:
                return set_name
        
        for set_name in ONE_PIECE_SETS:
            if set_name.lower() in name_lower:
                return set_name
        
        return None
    
    async def _apply_rate_limit(self):
        """Apply rate limiting delay between requests."""
        if self._last_request_time is not None:
            elapsed = asyncio.get_event_loop().time() - self._last_request_time
            delay = random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX)
            if elapsed < delay:
                await asyncio.sleep(delay - elapsed)
        self._last_request_time = asyncio.get_event_loop().time()
    
    async def _make_request(self, url: str, method: str = 'GET', **kwargs) -> Optional[aiohttp.ClientResponse]:
        """Make HTTP request with circuit breaker, rate limiting, and retry logic."""
        # Check circuit breaker
        if not self._circuit_breaker.can_execute():
            logger.warning(f"{self.retailer_name}: Circuit breaker is OPEN, skipping request")
            return None
        
        await self._apply_rate_limit()
        
        for attempt in range(RETRY_ATTEMPTS):
            try:
                logger.debug(f"{self.retailer_name}: {method} {url} (attempt {attempt + 1}/{RETRY_ATTEMPTS})")
                
                if method.upper() == 'GET':
                    async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT), **kwargs) as response:
                        if response.status == 200:
                            self._circuit_breaker.record_success()
                            return response
                        elif response.status == 429:  # Rate limited
                            retry_after = int(response.headers.get('Retry-After', RETRY_DELAY_BASE * (2 ** attempt)))
                            logger.warning(f"{self.retailer_name}: Rate limited (429), waiting {retry_after}s")
                            await asyncio.sleep(retry_after)
                        elif response.status >= 500:  # Server error
                            logger.warning(f"{self.retailer_name}: Server error {response.status}")
                            if attempt < RETRY_ATTEMPTS - 1:
                                backoff = RETRY_DELAY_BASE * (2 ** attempt) + random.uniform(0, 1)
                                await asyncio.sleep(backoff)
                        else:
                            logger.warning(f"{self.retailer_name}: HTTP {response.status} for {url}")
                            
            except asyncio.TimeoutError:
                logger.warning(f"{self.retailer_name}: Timeout on attempt {attempt + 1}")
            except aiohttp.ClientError as e:
                logger.warning(f"{self.retailer_name}: Client error on attempt {attempt + 1}: {e}")
            except Exception as e:
                logger.error(f"{self.retailer_name}: Unexpected error on attempt {attempt + 1}: {e}")
            
            if attempt < RETRY_ATTEMPTS - 1:
                backoff = RETRY_DELAY_BASE * (2 ** attempt) + random.uniform(0, 1)
                logger.info(f"{self.retailer_name}: Retrying in {backoff:.1f}s...")
                await asyncio.sleep(backoff)
        
        # All attempts failed
        self._circuit_breaker.record_failure()
        logger.error(f"{self.retailer_name}: All {RETRY_ATTEMPTS} attempts failed for {url}")
        return None
    
    async def _fetch_page(self, url: str) -> Optional[BeautifulSoup]:
        """Fetch and parse a page."""
        response = await self._make_request(url)
        if not response:
            return None
        
        try:
            html = await response.text()
            return BeautifulSoup(html, 'html.parser')
        except Exception as e:
            logger.error(f"{self.retailer_name}: Failed to parse HTML: {e}")
            return None
    
    @abstractmethod
    async def search_products(self, query: str) -> List[Product]:
        """Search for products. Must be implemented by subclasses."""
        pass
    
    @abstractmethod
    async def get_product_details(self, url: str) -> Optional[Product]:
        """Get detailed product info. Must be implemented by subclasses."""
        pass
    
    async def __aenter__(self):
        """Async context manager entry."""
        self.session = aiohttp.ClientSession(headers=self._headers)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()
            self.session = None
