from typing import List, Optional
from models import Product
from scrapers.base import BaseScraper
from bs4 import BeautifulSoup

class KmartScraper(BaseScraper):
    """Scraper for Kmart Australia"""
    
    def __init__(self):
        super().__init__('Kmart', 'https://www.kmart.com.au')
    
    async def search_products(self, query: str) -> List[Product]:
        """Search Kmart for products"""
        products = []
        search_url = f"https://www.kmart.com.au/search/?q={query.replace(' ', '+')}"
        
        try:
            async with self.session.get(search_url, timeout=30) as response:
                if response.status == 200:
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    # Kmart product items
                    product_items = soup.find_all('div', class_='product-item')
                    
                    for item in product_items:
                        product = self._parse_product_item(item)
                        if product and self._is_tcgp_product(product.name):
                            products.append(product)
        
        except Exception as e:
            print(f"Error searching Kmart: {e}")
        
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
            name_elem = item.find('h3', class_='product-name') or item.find('a', class_='product-title')
            name = name_elem.text.strip() if name_elem else 'Unknown Product'
            
            # Product ID
            product_id = self._generate_product_id(url)
            
            # Price
            price_elem = item.find('span', class_='price')
            price = None
            if price_elem:
                price = self._extract_price(price_elem.text)
            
            # Stock status
            stock_elem = item.find('div', class_='stock-status')
            in_stock = False
            if stock_elem:
                stock_text = stock_elem.text.lower()
                in_stock = 'in stock' in stock_text
            
            # Check for cart button
            cart_btn = item.find('button', class_='add-to-cart')
            if cart_btn and not cart_btn.get('disabled'):
                in_stock = True
            
            # Image
            img_elem = item.find('img', class_='product-image')
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
            print(f"Error parsing Kmart product: {e}")
            return None
    
    async def get_product_details(self, url: str) -> Optional[Product]:
        """Get detailed product info from product page"""
        try:
            async with self.session.get(url, timeout=30) as response:
                if response.status == 200:
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    # Product name
                    name_elem = soup.find('h1', class_='product-title')
                    name = name_elem.text.strip() if name_elem else 'Unknown'
                    
                    # Price
                    price_elem = soup.find('span', class_='price')
                    price = None
                    if price_elem:
                        price = self._extract_price(price_elem.text)
                    
                    # Stock status
                    stock_elem = soup.find('div', class_='stock-status')
                    in_stock = False
                    if stock_elem:
                        stock_text = stock_elem.text.lower()
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
            print(f"Error getting Kmart product details: {e}")
        
        return None
