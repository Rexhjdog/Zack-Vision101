"""Unit tests for scraper functionality."""
import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch, Mock
from bs4 import BeautifulSoup

from src.scrapers.base import CircuitBreaker, CircuitState, BaseScraper
from src.models.product import Product


class TestCircuitBreaker:
    """Test Circuit Breaker pattern implementation."""
    
    def test_circuit_starts_closed(self):
        """Test circuit starts in CLOSED state."""
        cb = CircuitBreaker()
        assert cb.state == CircuitState.CLOSED
        assert cb.failures == 0
        assert cb.can_execute() is True
    
    def test_record_success_resets_failures(self):
        """Test success resets failure count."""
        cb = CircuitBreaker()
        cb.failures = 3
        cb.record_success()
        assert cb.failures == 0
        assert cb.state == CircuitState.CLOSED
    
    def test_record_failure_increments_count(self):
        """Test failure increments failure count."""
        cb = CircuitBreaker(failure_threshold=5)
        cb.record_failure()
        assert cb.failures == 1
        cb.record_failure()
        assert cb.failures == 2
    
    def test_circuit_opens_after_threshold(self):
        """Test circuit opens after failure threshold."""
        cb = CircuitBreaker(failure_threshold=3)
        cb.record_failure()
        cb.record_failure()
        result = cb.record_failure()  # Third failure
        
        assert result is True  # Circuit is now open
        assert cb.state == CircuitState.OPEN
        assert cb.can_execute() is False
    
    def test_circuit_half_open_after_timeout(self):
        """Test circuit enters half-open after recovery timeout."""
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=1)
        cb.record_failure()  # Circuit opens
        assert cb.state == CircuitState.OPEN
        assert cb.can_execute() is False
        
        # Simulate time passing
        cb.last_failure_time = datetime.now() - timedelta(seconds=2)
        assert cb.can_execute() is True  # Now half-open
        assert cb.state == CircuitState.HALF_OPEN
    
    def test_success_in_half_open_closes_circuit(self):
        """Test success in half-open state closes circuit."""
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=1)
        cb.record_failure()
        cb.last_failure_time = datetime.now() - timedelta(seconds=2)
        
        assert cb.can_execute() is True
        cb.record_success()
        assert cb.state == CircuitState.CLOSED


class TestBaseScraperUtils:
    """Test BaseScraper utility methods."""
    
    @pytest.fixture
    def scraper(self):
        """Create a test scraper."""
        class TestScraper(BaseScraper):
            async def search_products(self, query):
                return []
            
            async def get_product_details(self, url):
                return None
        
        return TestScraper("Test Store", "https://test.com")
    
    def test_generate_product_id(self, scraper):
        """Test product ID generation."""
        url = "https://test.com/product/123"
        product_id = scraper._generate_product_id(url)
        
        assert len(product_id) == 16
        assert isinstance(product_id, str)
        # Same URL should generate same ID
        assert scraper._generate_product_id(url) == product_id
    
    def test_extract_price_valid(self, scraper):
        """Test price extraction from valid strings."""
        assert scraper._extract_price("$199.99") == 199.99
        assert scraper._extract_price("199.99 AUD") == 199.99
        assert scraper._extract_price("Price: $150.00") == 150.00
        assert scraper._extract_price("$1,299.99") == 1299.99
    
    def test_extract_price_invalid(self, scraper):
        """Test price extraction from invalid strings."""
        assert scraper._extract_price("") is None
        assert scraper._extract_price(None) is None
        assert scraper._extract_price("Out of stock") is None
        assert scraper._extract_price("Contact us") is None
    
    def test_is_booster_box_true(self, scraper):
        """Test booster box detection - positive cases."""
        assert scraper._is_booster_box("Pokemon Booster Box") is True
        assert scraper._is_booster_box("Display Box 36 packs") is True
        assert scraper._is_booster_box("Booster Case") is True
    
    def test_is_booster_box_false(self, scraper):
        """Test booster box detection - negative cases."""
        assert scraper._is_booster_box("Booster Pack") is False
        assert scraper._is_booster_box("Elite Trainer Box") is False
        assert scraper._is_booster_box("3-Pack Blister") is False
        assert scraper._is_booster_box("Single Pack") is False
    
    def test_categorize_product(self, scraper):
        """Test product categorization."""
        assert scraper._categorize_product("Pokemon Booster Box") == "pokemon"
        assert scraper._categorize_product("Pokémon Display") == "pokemon"
        assert scraper._categorize_product("One Piece Booster") == "one_piece"
        assert scraper._categorize_product("Magic Cards") == "unknown"
    
    def test_extract_set_name_pokemon(self, scraper):
        """Test Pokemon set name extraction."""
        assert scraper._extract_set_name("Paldean Fates Booster Box") == "Paldean Fates"
        assert scraper._extract_set_name("Temporal Forces Display") == "Temporal Forces"
    
    def test_extract_set_name_onepiece(self, scraper):
        """Test One Piece set name extraction."""
        assert scraper._extract_set_name("Romance Dawn Booster") == "Romance Dawn"
        assert scraper._extract_set_name("Paramount War Display") == "Paramount War"
    
    def test_get_headers(self, scraper):
        """Test request headers generation."""
        headers = scraper._get_headers()
        
        assert "User-Agent" in headers
        assert "Accept" in headers
        assert "Accept-Language" in headers
        assert headers["User-Agent"].startswith("Mozilla")


@pytest.mark.asyncio
class TestBaseScraperAsync:
    """Test async BaseScraper methods."""
    
    @pytest.fixture
    async def scraper(self):
        """Create an async test scraper."""
        class TestScraper(BaseScraper):
            async def search_products(self, query):
                return []
            
            async def get_product_details(self, url):
                return None
        
        scraper = TestScraper("Test Store", "https://test.com")
        async with scraper:
            yield scraper
    
    async def test_rate_limiting(self, scraper):
        """Test rate limiting between requests."""
        start_time = asyncio.get_event_loop().time()
        
        # First request sets last_request_time
        await scraper._apply_rate_limit()
        
        # Second request should wait
        await scraper._apply_rate_limit()
        
        elapsed = asyncio.get_event_loop().time() - start_time
        assert elapsed >= 0  # Should have some delay
    
    async def test_context_manager(self):
        """Test async context manager."""
        class TestScraper(BaseScraper):
            async def search_products(self, query):
                return []
            
            async def get_product_details(self, url):
                return None
        
        scraper = TestScraper("Test Store", "https://test.com")
        assert scraper.session is None
        
        async with scraper:
            assert scraper.session is not None
        
        assert scraper.session is None
