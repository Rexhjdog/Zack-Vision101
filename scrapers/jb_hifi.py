from scrapers.base import BaseScraper


class JBHiFiScraper(BaseScraper):
    """Scraper for JB Hi-Fi Australia.

    NOTE: CSS selectors are best-effort placeholders. They must be verified
    against the live JB Hi-Fi site and updated if the HTML structure differs.
    """

    SEARCH_SELECTORS = {
        'container': ('div', {'class': 'product-tile'}),
        'link': ('a', {'class': 'product-tile-link'}),
        'name': ('h3', {'class': 'product-tile-title'}),
        'price': [('span', {'class': 'price'}), ('div', {'class': 'product-tile-price'})],
        'stock': ('div', {'class': 'availability'}),
        'image': ('img', {'class': 'product-image'}),
        'cart_button': ('button', {'class': 'add-to-cart'}),
    }

    DETAIL_SELECTORS = {
        'name': ('h1', {'class': 'product-title'}),
        'price': [('span', {'class': 'price'}), ('div', {'class': 'product-price'})],
        'stock': ('div', {'class': 'availability'}),
        'cart_button': ('button', {'id': 'add-to-cart'}),
    }

    IN_STOCK_KEYWORDS = ['in stock', 'available', 'online']

    def __init__(self):
        super().__init__('JB Hi-Fi', 'https://www.jbhifi.com.au')

    def _build_search_url(self, query: str) -> str:
        return f"{self.base_url}/search?page=1&query={query.replace(' ', '%20')}"
