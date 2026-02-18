"""EB Games Australia scraper."""

from __future__ import annotations

import logging

from bs4 import BeautifulSoup, Tag

from src.models.product import Product
from src.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)


class EBGamesScraper(BaseScraper):
    def __init__(self) -> None:
        super().__init__("eb_games", "EB Games", "https://www.ebgames.com.au")

    def _parse_products(self, soup: BeautifulSoup, category: str) -> list[Product]:
        products: list[Product] = []

        # Primary selector: product cards
        cards = soup.select(".product-card, .product-tile, .search-result-item")
        if not cards:
            # Fallback: any link containing product info
            cards = soup.select("[data-product], .product")

        for card in cards:
            if not isinstance(card, Tag):
                continue

            name = self._extract_name(card)
            if not name:
                continue

            url = self._extract_url(card)
            if not url:
                continue

            price = self._extract_card_price(card)
            in_stock = self._check_stock(card)
            image_url = self._extract_image(card)

            products.append(
                self._build_product(
                    name,
                    url,
                    category,
                    price=price,
                    in_stock=in_stock,
                    image_url=image_url,
                )
            )

        return products

    @staticmethod
    def _extract_name(card: Tag) -> str:
        for sel in (".product-title", ".product-name", "h3", "h2", "[data-name]"):
            el = card.select_one(sel)
            if el and el.get_text(strip=True):
                return el.get_text(strip=True)
        return ""

    @staticmethod
    def _extract_url(card: Tag) -> str:
        link = card.select_one("a[href]")
        if link:
            return link["href"]
        if card.name == "a" and card.get("href"):
            return card["href"]
        return ""

    def _extract_card_price(self, card: Tag) -> float | None:
        for sel in (".price", ".product-price", "[data-price]"):
            el = card.select_one(sel)
            if el:
                price = self._extract_price(el.get_text())
                if price is not None:
                    return price
        return None

    @staticmethod
    def _check_stock(card: Tag) -> bool:
        stock_el = card.select_one(
            ".stock-status, .availability, [data-available]"
        )
        if stock_el:
            text = stock_el.get_text(strip=True).lower()
            return "out of stock" not in text and "unavailable" not in text

        btn = card.select_one("button.add-to-cart, .btn-add-to-cart")
        if btn:
            disabled = btn.get("disabled") is not None
            return not disabled

        return False

    @staticmethod
    def _extract_image(card: Tag) -> str:
        img = card.select_one("img[src], img[data-src]")
        if img:
            return img.get("src") or img.get("data-src") or ""
        return ""
