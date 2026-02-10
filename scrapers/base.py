import hashlib
import random
import asyncio
import logging
from typing import List, Optional
from models import Product
from config import (
    USER_AGENTS, REQUEST_DELAY_MIN, REQUEST_DELAY_MAX,
    REQUEST_TIMEOUT, RETRY_ATTEMPTS, RETRY_DELAY_BASE,
    BOOSTER_BOX_KEYWORDS, EXCLUDE_KEYWORDS,
    POKEMON_SETS, ONE_PIECE_SETS,
)
import aiohttp
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class BaseScraper:
    """Base class for all retail scrapers.

    Subclasses define CSS selectors via SEARCH_SELECTORS and DETAIL_SELECTORS,
    and the base class handles fetching, parsing, and product construction.
    Override _parse_product_item or _parse_product_detail if a retailer
    needs non-standard parsing logic.
    """

    # Subclasses override these with retailer-specific CSS selectors.
    # Each value is (tag, attrs_dict) for BeautifulSoup.find / find_all.
    SEARCH_SELECTORS = {
        'container': ('div', {'class': 'product-item'}),
        'link': ('a', {'class': 'product-link'}),
        'name': [('h3', {'class': 'product-title'}), ('a', {'class': 'product-name'})],
        'price': [('span', {'class': 'price'}), ('div', {'class': 'product-price'})],
        'stock': [('div', {'class': 'stock-status'}), ('span', {'class': 'availability'})],
        'image': ('img', {}),
        'cart_button': ('button', {'class': 'add-to-cart'}),
    }

    DETAIL_SELECTORS = {
        'name': ('h1', {'class': 'product-title'}),
        'price': [('span', {'class': 'price'}), ('div', {'class': 'product-price'})],
        'stock': ('div', {'class': 'stock-status'}),
        'cart_button': ('button', {'id': 'add-to-cart'}),
    }

    IN_STOCK_KEYWORDS = ['in stock', 'available']

    def __init__(self, retailer_name: str, base_url: str):
        self.retailer_name = retailer_name
        self.base_url = base_url
        self.session: Optional[aiohttp.ClientSession] = None
        self._last_request_time: Optional[float] = None

    def _generate_product_id(self, url: str) -> str:
        """Generate deterministic product ID from retailer name and URL"""
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

    def _build_search_url(self, query: str) -> str:
        """Build search URL for this retailer. Subclasses should override."""
        return f"{self.base_url}/search?q={query.replace(' ', '+')}"

    # ──────────────────────────────────────────
    # Product classification helpers
    # ──────────────────────────────────────────

    def _extract_price(self, price_text: str) -> Optional[float]:
        """Extract price from text"""
        if not price_text:
            return None
        price_text = price_text.replace('$', '').replace('AUD', '').replace(',', '').strip()
        try:
            return float(price_text)
        except ValueError:
            return None

    def _is_tcgp_product(self, name: str) -> bool:
        """Check if product is a booster box ONLY (no packs)"""
        name_lower = name.lower()
        if any(kw in name_lower for kw in EXCLUDE_KEYWORDS):
            return False
        return any(kw in name_lower for kw in BOOSTER_BOX_KEYWORDS)

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
        name_lower = name.lower()
        for set_name in POKEMON_SETS:
            if set_name.lower() in name_lower:
                return set_name
        for set_name in ONE_PIECE_SETS:
            if set_name.lower() in name_lower:
                return set_name
        return None

    # ──────────────────────────────────────────
    # HTTP helpers
    # ──────────────────────────────────────────

    async def _apply_rate_limit(self):
        """Apply rate limiting delay between requests"""
        loop = asyncio.get_running_loop()
        if self._last_request_time is not None:
            elapsed = loop.time() - self._last_request_time
            delay = random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX)
            if elapsed < delay:
                await asyncio.sleep(delay - elapsed)
        self._last_request_time = loop.time()

    async def _fetch_page(self, url: str) -> Optional[str]:
        """Fetch a page and return its HTML content.

        Returns the HTML string on success, or None on failure.
        This fixes the previous bug where a response object was returned
        from inside an `async with` block (which closes the response).
        """
        await self._apply_rate_limit()
        timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)

        for attempt in range(RETRY_ATTEMPTS):
            try:
                logger.debug(f"{self.retailer_name}: GET {url} (attempt {attempt + 1}/{RETRY_ATTEMPTS})")

                async with self.session.get(url, timeout=timeout) as response:
                    if response.status == 200:
                        return await response.text()
                    elif response.status == 429:
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

    # ──────────────────────────────────────────
    # Selector helpers
    # ──────────────────────────────────────────

    @staticmethod
    def _find_with_fallbacks(element, selectors) -> Optional:
        """Try multiple selectors, return first match.

        `selectors` can be a single (tag, attrs) tuple or a list of them.
        """
        if isinstance(selectors, tuple) and len(selectors) == 2 and isinstance(selectors[1], dict):
            selectors = [selectors]
        for tag, attrs in selectors:
            result = element.find(tag, attrs)
            if result:
                return result
        return None

    # ──────────────────────────────────────────
    # Search & detail parsing (shared logic)
    # ──────────────────────────────────────────

    async def search_products(self, query: str) -> List[Product]:
        """Search for products on the retailer's site"""
        products = []
        search_url = self._build_search_url(query)

        try:
            html = await self._fetch_page(search_url)
            if not html:
                logger.warning(f"Failed to fetch search results from {self.retailer_name}")
                return products

            soup = BeautifulSoup(html, 'html.parser')

            tag, attrs = self.SEARCH_SELECTORS['container']
            product_items = soup.find_all(tag, attrs)

            if not product_items:
                logger.warning(
                    f"No products found with selector '{tag}.{attrs.get('class', '')}' "
                    f"on {self.retailer_name} — selectors may need updating"
                )

            for item in product_items:
                try:
                    product = self._parse_product_item(item)
                    if product and self._is_tcgp_product(product.name):
                        products.append(product)
                except Exception as e:
                    logger.error(f"Error parsing product item: {e}")
                    continue

            logger.info(f"{self.retailer_name}: Found {len(products)} booster boxes")

        except Exception as e:
            logger.error(f"Error searching {self.retailer_name}: {e}", exc_info=True)

        return products

    def _parse_product_item(self, item) -> Optional[Product]:
        """Parse a product item from a search results page.

        Uses SEARCH_SELECTORS. Subclasses can override for custom logic.
        """
        try:
            sel = self.SEARCH_SELECTORS

            # Link
            link_elem = self._find_with_fallbacks(item, sel['link'])
            if not link_elem:
                return None
            url = link_elem.get('href', '')
            if url and not url.startswith('http'):
                url = f"{self.base_url}{url}"

            # Name
            name_elem = self._find_with_fallbacks(item, sel['name'])
            name = name_elem.text.strip() if name_elem else 'Unknown Product'

            # Price
            price_elem = self._find_with_fallbacks(item, sel['price'])
            price = self._extract_price(price_elem.text) if price_elem else None

            # Stock status
            in_stock = False
            stock_elem = self._find_with_fallbacks(item, sel['stock'])
            if stock_elem:
                stock_text = stock_elem.text.lower()
                in_stock = any(kw in stock_text for kw in self.IN_STOCK_KEYWORDS)

            # Cart button fallback
            cart_sel = sel.get('cart_button')
            if cart_sel:
                cart_elem = self._find_with_fallbacks(item, cart_sel)
                if cart_elem and not cart_elem.get('disabled'):
                    in_stock = True

            # Image
            img_sel = sel.get('image', ('img', {}))
            img_elem = self._find_with_fallbacks(item, img_sel)
            image_url = img_elem.get('src') if img_elem else None

            return Product(
                id=self._generate_product_id(url),
                name=name,
                retailer=self.retailer_name,
                url=url,
                price=price,
                in_stock=in_stock,
                image_url=image_url,
                category=self._categorize_product(name),
                set_name=self._extract_set_name(name),
                pack_type='box',
            )

        except Exception as e:
            logger.error(f"Error parsing product item: {e}")
            return None

    async def get_product_details(self, url: str) -> Optional[Product]:
        """Get detailed product info from a product page.

        Uses DETAIL_SELECTORS. Subclasses can override for custom logic.
        """
        try:
            html = await self._fetch_page(url)
            if not html:
                return None

            soup = BeautifulSoup(html, 'html.parser')
            sel = self.DETAIL_SELECTORS

            # Name
            name_elem = self._find_with_fallbacks(soup, sel['name'])
            name = name_elem.text.strip() if name_elem else 'Unknown'

            # Price
            price_elem = self._find_with_fallbacks(soup, sel['price'])
            price = self._extract_price(price_elem.text) if price_elem else None

            # Stock status
            in_stock = False
            stock_elem = self._find_with_fallbacks(soup, sel['stock'])
            if stock_elem:
                stock_text = stock_elem.text.lower()
                in_stock = any(kw in stock_text for kw in self.IN_STOCK_KEYWORDS)

            # Cart button fallback
            cart_sel = sel.get('cart_button')
            if cart_sel:
                cart_elem = self._find_with_fallbacks(soup, cart_sel)
                if cart_elem and not cart_elem.get('disabled'):
                    in_stock = True

            return Product(
                id=self._generate_product_id(url),
                name=name,
                retailer=self.retailer_name,
                url=url,
                price=price,
                in_stock=in_stock,
                category=self._categorize_product(name),
                set_name=self._extract_set_name(name),
                pack_type='box',
            )

        except Exception as e:
            logger.error(f"Error getting product details from {self.retailer_name}: {e}")
            return None

    # ──────────────────────────────────────────
    # Context manager
    # ──────────────────────────────────────────

    async def __aenter__(self):
        """Async context manager entry"""
        self.session = aiohttp.ClientSession(headers=self._get_headers())
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()
            self.session = None
