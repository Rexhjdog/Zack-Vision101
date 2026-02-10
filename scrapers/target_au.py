from scrapers.base import BaseScraper


class TargetScraper(BaseScraper):
    """Scraper for Target Australia.

    NOTE: CSS selectors are best-effort placeholders. They must be verified
    against the live Target AU site and updated if the HTML structure differs.
    """

    SEARCH_SELECTORS = {
        'container': ('div', {'class': 'product-item'}),
        'link': ('a', {'class': 'product-link'}),
        'name': ('a', {'class': 'product-name'}),
        'price': ('span', {'class': 'price'}),
        'stock': ('div', {'class': 'stock-availability'}),
        'image': ('img', {'class': 'product-image'}),
        'cart_button': ('button', {'class': 'add-to-cart'}),
    }

    DETAIL_SELECTORS = {
        'name': ('h1', {'class': 'product-name'}),
        'price': ('span', {'class': 'price'}),
        'stock': ('div', {'class': 'stock-availability'}),
    }

    def __init__(self):
        super().__init__('Target', 'https://www.target.com.au')

    def _build_search_url(self, query: str) -> str:
        return f"{self.base_url}/search?text={query.replace(' ', '+')}"
