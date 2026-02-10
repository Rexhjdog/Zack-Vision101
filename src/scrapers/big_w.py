"""Big W Australia scraper."""
import logging
from typing import List, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from src.scrapers.base import BaseScraper
from src.models.product import Product

logger = logging.getLogger(__name__)


class BigWScraper(BaseScraper):
    """Scraper for Big W Australia."""
    
    def __init__(self):
        super().__init__('Big W', 'https://www.bigw.com.au')
    
    async def search_products(self, query: str) -> List[Product]:
        """Search Big W for products."""
        products = []
        search_url = f"{self.base_url}/search?q={query.replace(' ', '+')}"
        
        soup = await self._fetch_page(search_url)
        if not soup:
            return products
        
        try:
            product_selectors = [
                'div.product-item',
                'article.product',
                '.product-list-item',
                '.product-card',
            ]
            
            product_items = []
            for selector in product_selectors:
                product_items = soup.select(selector)
                if product_items:
                    break
            
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
            link_elem = (
                item.select_one('a.product-link') or
                item.select_one('a[href*="/product/"]') or
                item.select_one('a')
            )
            
            if not link_elem:
                return None
            
            href = link_elem.get('href', '')
            url = urljoin(self.base_url, href)
            
            name_elem = (
                item.select_one('h3.product-name') or
                item.select_one('.product-title') or
                link_elem
            )
            
            name = name_elem.get_text(strip=True) if name_elem else 'Unknown Product'
            if not name or name == 'Unknown Product':
                return None
            
            product_id = self._generate_product_id(url)
            
            price_elem = (
                item.select_one('span.price') or
                item.select_one('.product-price')
            )
            
            price = None
            if price_elem:
                price = self._extract_price(price_elem.get_text(strip=True))
            
            in_stock = False
            stock_elem = item.select_one('span.availability')
            if stock_elem:
                stock_text = stock_elem.get_text(strip=True).lower()
                in_stock = 'in stock' in stock_text
            
            add_cart = item.select_one('button.add-to-cart')
            if add_cart and not add_cart.get('disabled'):
                in_stock = True
            
            img_elem = item.select_one('img.product-image') or item.select_one('img')
            image_url = img_elem.get('src') if img_elem else None
            
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
            name_elem = soup.select_one('h1.product-title') or soup.select_one('h1')
            name = name_elem.get_text(strip=True) if name_elem else 'Unknown'
            
            price_elem = soup.select_one('span.price')
            price = self._extract_price(price_elem.get_text(strip=True)) if price_elem else None
            
            in_stock = False
            stock_elem = soup.select_one('div.availability')
            if stock_elem:
                stock_text = stock_elem.get_text(strip=True).lower()
                in_stock = 'in stock' in stock_text
            
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
