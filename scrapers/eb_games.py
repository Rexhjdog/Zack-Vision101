from scrapers.base import BaseScraper


class EBGamesScraper(BaseScraper):
    """Scraper for EB Games Australia.

    NOTE: CSS selectors are best-effort placeholders. They must be verified
    against the live EB Games site and updated if the HTML structure differs.
    """

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

    def __init__(self):
        super().__init__('EB Games', 'https://www.ebgames.com.au')

    def _build_search_url(self, query: str) -> str:
        return f"{self.base_url}/search?q={query.replace(' ', '+')}"
