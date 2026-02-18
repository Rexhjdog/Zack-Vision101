"""JB Hi-Fi Australia scraper."""

from __future__ import annotations

import logging

from bs4 import BeautifulSoup, Tag

from src.models.product import Product
from src.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)


class JBHiFiScraper(BaseScraper):
    def __init__(self) -> None:
        super().__init__("jb_hifi", "JB Hi-Fi", "https://www.jbhifi.com.au")

    def _parse_products(self, soup: BeautifulSoup, category: str) -> list[Product]:
        products: list[Product] = []

        cards = soup.select(
            ".product-tile, .product-card, .search-result-product, [data-product-id]"
        )
        if not cards:
            cards = soup.select(".product, .item")

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
        for sel in (
            ".product-title",
            ".product-tile__title",
            "h3 a",
            "h2 a",
            "[data-product-name]",
        ):
            el = card.select_one(sel)
            if el and el.get_text(strip=True):
                return el.get_text(strip=True)
        return ""

    @staticmethod
    def _extract_url(card: Tag) -> str:
        for sel in ("a.product-tile__link", "a[href]"):
            link = card.select_one(sel)
            if link and link.get("href"):
                return link["href"]
        return ""

    def _extract_card_price(self, card: Tag) -> float | None:
        for sel in (
            ".product-tile__price",
            ".price",
            "[data-price]",
            ".amount",
        ):
            el = card.select_one(sel)
            if el:
                price = self._extract_price(el.get_text())
                if price is not None:
                    return price
        return None

    @staticmethod
    def _check_stock(card: Tag) -> bool:
        oos = card.select_one(".out-of-stock, .sold-out, .unavailable")
        if oos:
            return False

        btn = card.select_one(
            "button.add-to-cart, .product-tile__add-to-cart, [data-add-to-cart]"
        )
        if btn:
            return btn.get("disabled") is None

        return False

    @staticmethod
    def _extract_image(card: Tag) -> str:
        img = card.select_one("img[src], img[data-src], img[data-lazy]")
        if img:
            return img.get("src") or img.get("data-src") or img.get("data-lazy") or ""
        return ""
