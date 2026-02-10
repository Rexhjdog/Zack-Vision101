from scrapers.base import BaseScraper


class KmartScraper(BaseScraper):
    """Scraper for Kmart Australia.

    NOTE: CSS selectors are best-effort placeholders. They must be verified
    against the live Kmart site and updated if the HTML structure differs.
    """

    SEARCH_SELECTORS = {
        'container': ('div', {'class': 'product-item'}),
        'link': ('a', {'class': 'product-link'}),
        'name': [('h3', {'class': 'product-name'}), ('a', {'class': 'product-title'})],
        'price': ('span', {'class': 'price'}),
        'stock': ('div', {'class': 'stock-status'}),
        'image': ('img', {'class': 'product-image'}),
        'cart_button': ('button', {'class': 'add-to-cart'}),
    }

    DETAIL_SELECTORS = {
        'name': ('h1', {'class': 'product-title'}),
        'price': ('span', {'class': 'price'}),
        'stock': ('div', {'class': 'stock-status'}),
    }

    def __init__(self):
        super().__init__('Kmart', 'https://www.kmart.com.au')

    def _build_search_url(self, query: str) -> str:
        return f"{self.base_url}/search/?q={query.replace(' ', '+')}"
