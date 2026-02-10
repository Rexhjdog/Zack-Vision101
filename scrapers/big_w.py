from scrapers.base import BaseScraper


class BigWScraper(BaseScraper):
    """Scraper for Big W Australia.

    NOTE: CSS selectors are best-effort placeholders. They must be verified
    against the live Big W site and updated if the HTML structure differs.
    """

    SEARCH_SELECTORS = {
        'container': ('div', {'class': 'product-item'}),
        'link': ('a', {'class': 'product-link'}),
        'name': ('h3', {'class': 'product-name'}),
        'price': [('span', {'class': 'price'}), ('div', {'class': 'product-price'})],
        'stock': ('span', {'class': 'availability'}),
        'image': ('img', {'class': 'product-image'}),
        'cart_button': ('button', {'class': 'add-to-cart'}),
    }

    DETAIL_SELECTORS = {
        'name': ('h1', {'class': 'product-title'}),
        'price': ('span', {'class': 'price'}),
        'stock': ('div', {'class': 'availability'}),
    }

    def __init__(self):
        super().__init__('Big W', 'https://www.bigw.com.au')

    def _build_search_url(self, query: str) -> str:
        return f"{self.base_url}/search?q={query.replace(' ', '+')}"
