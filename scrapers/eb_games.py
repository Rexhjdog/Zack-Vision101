from typing import List, Optional
import logging
from models import Product
from scrapers.base import BaseScraper
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

class EBGamesScraper(BaseScraper):
    """Scraper for EB Games Australia"""
    
    def __init__(self):
        super().__init__('EB Games', 'https://www.ebgames.com.au')
    
    async def search_products(self, query: str) -> List[Product]:
        """Search EB Games for products"""
        products = []
        search_url = f"https://www.ebgames.com.au/search?q={query.replace(' ', '+')}"
        
        try:
            response = await self._make_request(search_url)
            if not response:
                logger.warning(f"Failed to fetch search results from {self.retailer_name}")
                return products
            
            html = await response.text()
            soup = BeautifulSoup(html, 'html.parser')
            
            # EB Games product grid - these selectors need to be verified
            product_items = soup.find_all('div', class_='product-item')
            
            if not product_items:
                logger.warning(f"No products found with selector 'div.product-item' on {self.retailer_name}")
            
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
        """Parse a product item from the page"""
        try:
            # Product link
            link_elem = item.find('a', class_='product-link')
            if not link_elem:
                return None
            
            url = link_elem.get('href', '')
            if not url.startswith('http'):
                url = f"{self.base_url}{url}"
            
            # Product name
            name_elem = item.find('h3', class_='product-title') or item.find('a', class_='product-name')
            name = name_elem.text.strip() if name_elem else 'Unknown Product'
            
            # Product ID
            product_id = self._generate_product_id(url)
            
            # Price
            price_elem = item.find('span', class_='price') or item.find('div', class_='product-price')
            price = None
            if price_elem:
                price_text = price_elem.text.strip()
                price = self._extract_price(price_text)
            
            # Stock status
            stock_elem = item.find('div', class_='stock-status') or item.find('span', class_='availability')
            in_stock = False
            if stock_elem:
                stock_text = stock_elem.text.lower()
                in_stock = 'in stock' in stock_text or 'available' in stock_text
            
            # Image
            img_elem = item.find('img')
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
                pack_type=self._get_product_type(name)
            )
        
        except Exception as e:
            logger.error(f"Error parsing product item: {e}")
            return None
    
    async def get_product_details(self, url: str) -> Optional[Product]:
        """Get detailed product info from product page"""
        try:
            response = await self._make_request(url)
            if not response:
                return None
            
            html = await response.text()
            soup = BeautifulSoup(html, 'html.parser')
            
            # Product name
            name_elem = soup.find('h1', class_='product-title')
            name = name_elem.text.strip() if name_elem else 'Unknown'
            
            # Price
            price_elem = soup.find('span', class_='price') or soup.find('div', class_='product-price')
            price = None
            if price_elem:
                price = self._extract_price(price_elem.text)
            
            # Stock status
            stock_elem = soup.find('div', class_='stock-status')
            in_stock = False
            if stock_elem:
                in_stock = 'in stock' in stock_elem.text.lower()
            
            # Add to cart button
            add_cart_btn = soup.find('button', {'id': 'add-to-cart'})
            if add_cart_btn and not add_cart_btn.get('disabled'):
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
