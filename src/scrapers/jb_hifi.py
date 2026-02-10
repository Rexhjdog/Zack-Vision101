"""JB Hi-Fi Australia scraper."""
import logging
from typing import List, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from src.scrapers.base import BaseScraper
from src.models.product import Product

logger = logging.getLogger(__name__)


class JBHiFiScraper(BaseScraper):
    """Scraper for JB Hi-Fi Australia."""
    
    def __init__(self):
        super().__init__('JB Hi-Fi', 'https://www.jbhifi.com.au')
    
    async def search_products(self, query: str) -> List[Product]:
        """Search JB Hi-Fi for products."""
        products = []
        search_url = f"{self.base_url}/search?page=1&query={query.replace(' ', '%20')}"
        
        soup = await self._fetch_page(search_url)
        if not soup:
            logger.warning(f"Failed to fetch search results from {self.retailer_name}")
            return products
        
        try:
            # Try multiple selectors
            product_selectors = [
                'div.product-tile',
                'article.product',
                'div.product-item',
                '[data-testid="product-tile"]',
                '.product-card',
            ]
            
            product_items = []
            for selector in product_selectors:
                product_items = soup.select(selector)
                if product_items:
                    logger.debug(f"Found {len(product_items)} products with selector: {selector}")
                    break
            
            if not product_items:
                logger.warning(f"No products found on {self.retailer_name}")
                return products
            
            for item in product_items:
                try:
                    product = self._parse_product_item(item)
                    if product and self._is_booster_box(product.name):
                        products.append(product)
                except Exception as e:
                    logger.error(f"Error parsing product item: {e}")
                    continue
            
            logger.info(f"{self.retailer_name}: Found {len(products)} booster boxes")
            
        except Exception as e:
            logger.error(f"Error searching {self.retailer_name}: {e}", exc_info=True)
        
        return products
    
    def _parse_product_item(self, item: BeautifulSoup) -> Optional[Product]:
        """Parse a product item from the page."""
        try:
            # Try multiple selectors for product link
            link_elem = (
                item.select_one('a.product-tile-link') or
                item.select_one('a[href*="/products/"]') or
                item.select_one('a') or
                item.find_parent('a')
            )
            
            if not link_elem:
                return None
            
            href = link_elem.get('href', '')
            if not href:
                return None
            
            url = urljoin(self.base_url, href)
            
            # Try multiple selectors for product name
            name_elem = (
                item.select_one('h3.product-tile-title') or
                item.select_one('h2.product-title') or
                item.select_one('.product-name') or
                item.select_one('[data-testid="product-name"]')
            )
            
            name = name_elem.get_text(strip=True) if name_elem else 'Unknown Product'
            if not name or name == 'Unknown Product':
                return None
            
            # Product ID
            product_id = self._generate_product_id(url)
            
            # Try multiple selectors for price
            price_elem = (
                item.select_one('span.price') or
                item.select_one('.product-tile-price') or
                item.select_one('[data-testid="price"]') or
                item.select_one('.current-price')
            )
            
            price = None
            if price_elem:
                price_text = price_elem.get_text(strip=True)
                price = self._extract_price(price_text)
            
            # Try multiple selectors for stock status
            in_stock = False
            stock_elem = (
                item.select_one('div.availability') or
                item.select_one('.stock-status') or
                item.select_one('[data-testid="availability"]')
            )
            
            if stock_elem:
                stock_text = stock_elem.get_text(strip=True).lower()
                in_stock = any(keyword in stock_text for keyword in ['in stock', 'available', 'online', 'add to cart'])
            
            # Check for add to cart button
            add_cart = item.select_one('button.add-to-cart, button[data-testid="add-to-cart"]')
            if add_cart and not add_cart.get('disabled'):
                in_stock = True
            
            # Try multiple selectors for image
            img_elem = item.select_one('img.product-image') or item.select_one('img')
            image_url = None
            if img_elem:
                image_url = (
                    img_elem.get('src') or
                    img_elem.get('data-src') or
                    img_elem.get('data-original')
                )
            
            return Product(
                id=product_id,
                name=name,
                retailer=self.retailer_name,
                url=url,
                price=price,
                in_stock=in_stock,
                image_url=image_url,
                category=self._categorize_product(name),
                set_name=self._extract_set_name(name),
                pack_type='box'
            )
        
        except Exception as e:
            logger.error(f"Error parsing product item: {e}")
            return None
    
    async def get_product_details(self, url: str) -> Optional[Product]:
        """Get detailed product info from product page."""
        soup = await self._fetch_page(url)
        if not soup:
            return None
        
        try:
            # Try multiple selectors for product name
            name_elem = (
                soup.select_one('h1.product-title') or
                soup.select_one('h1') or
                soup.select_one('[data-testid="product-title"]')
            )
            name = name_elem.get_text(strip=True) if name_elem else 'Unknown'
            
            # Try multiple selectors for price
            price_elem = (
                soup.select_one('span.price') or
                soup.select_one('.product-price') or
                soup.select_one('[data-testid="price"]')
            )
            price = self._extract_price(price_elem.get_text(strip=True)) if price_elem else None
            
            # Try multiple selectors for stock status
            in_stock = False
            stock_elem = (
                soup.select_one('div.availability') or
                soup.select_one('.stock-status') or
                soup.select_one('[data-testid="availability"]')
            )
            
            if stock_elem:
                stock_text = stock_elem.get_text(strip=True).lower()
                in_stock = any(keyword in stock_text for keyword in ['in stock', 'available', 'add to cart'])
            
            # Check add to cart button
            add_cart = soup.select_one('button#add-to-cart, button.add-to-cart')
            if add_cart and not add_cart.get('disabled'):
                in_stock = True
            
            return Product(
                id=self._generate_product_id(url),
                name=name,
                retailer=self.retailer_name,
                url=url,
                price=price,
                in_stock=in_stock,
                category=self._categorize_product(name),
                set_name=self._extract_set_name(name)
            )
        
        except Exception as e:
            logger.error(f"Error getting product details from {self.retailer_name}: {e}")
            return None
