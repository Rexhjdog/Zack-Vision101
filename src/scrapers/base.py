"""Base scraper with circuit-breaker, rate-limiting and retry logic."""

from __future__ import annotations

import asyncio
import logging
import random
import re
import time
from abc import ABC, abstractmethod
from urllib.parse import urljoin

import aiohttp
from bs4 import BeautifulSoup

from src.config import (
    BOOSTER_BOX_KEYWORDS,
    CIRCUIT_BREAKER_THRESHOLD,
    CIRCUIT_BREAKER_TIMEOUT,
    EXCLUSION_KEYWORDS,
    MAX_RETRIES,
    ONE_PIECE_SETS,
    POKEMON_SETS,
    REQUEST_DELAY_MAX,
    REQUEST_DELAY_MIN,
    REQUEST_TIMEOUT,
    USER_AGENTS,
)
from src.models.product import Product

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Circuit breaker
# ---------------------------------------------------------------------------

class CircuitBreaker:
    """Simple three-state circuit breaker (closed / open / half-open)."""

    def __init__(
        self,
        threshold: int = CIRCUIT_BREAKER_THRESHOLD,
        timeout: int = CIRCUIT_BREAKER_TIMEOUT,
    ) -> None:
        self.threshold = threshold
        self.timeout = timeout
        self.failures = 0
        self.last_failure: float = 0.0
        self.state: str = "closed"  # closed | open | half-open

    @property
    def is_open(self) -> bool:
        if self.state == "open":
            if time.monotonic() - self.last_failure >= self.timeout:
                self.state = "half-open"
                return False
            return True
        return False

    def record_success(self) -> None:
        self.failures = 0
        self.state = "closed"

    def record_failure(self) -> None:
        self.failures += 1
        self.last_failure = time.monotonic()
        if self.failures >= self.threshold:
            self.state = "open"
            logger.warning("Circuit breaker OPEN after %d failures", self.failures)


# ---------------------------------------------------------------------------
# Base scraper
# ---------------------------------------------------------------------------

_PRICE_RE = re.compile(r"\$\s*([\d,]+\.?\d*)")


class BaseScraper(ABC):
    """Abstract retailer scraper.

    Subclasses must implement ``_parse_products``.
    """

    def __init__(self, retailer_key: str, retailer_name: str, base_url: str) -> None:
        self.retailer_key = retailer_key
        self.retailer_name = retailer_name
        self.base_url = base_url
        self._cb = CircuitBreaker()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def search(
        self,
        category: str,
        search_path: str,
        *,
        session: aiohttp.ClientSession | None = None,
    ) -> list[Product]:
        """Fetch a search page and return parsed products."""
        if self._cb.is_open:
            logger.info(
                "[%s] Circuit breaker open – skipping %s search",
                self.retailer_name,
                category,
            )
            return []

        url = urljoin(self.base_url, search_path)
        html = await self._fetch(url, session=session)
        if html is None:
            return []

        soup = BeautifulSoup(html, "html.parser")
        try:
            products = self._parse_products(soup, category)
        except Exception:
            logger.exception("[%s] Parse error for %s", self.retailer_name, category)
            self._cb.record_failure()
            return []

        self._cb.record_success()
        return [p for p in products if self._is_booster_box(p.name)]

    # ------------------------------------------------------------------
    # Abstract
    # ------------------------------------------------------------------

    @abstractmethod
    def _parse_products(self, soup: BeautifulSoup, category: str) -> list[Product]:
        """Return a list of ``Product`` from the retailer's HTML."""

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    async def _fetch(
        self,
        url: str,
        *,
        session: aiohttp.ClientSession | None = None,
    ) -> str | None:
        """GET *url* with retries, rate-limiting and random user-agent."""
        own_session = session is None
        if own_session:
            session = aiohttp.ClientSession()

        try:
            for attempt in range(1, MAX_RETRIES + 1):
                await asyncio.sleep(
                    random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX)
                )
                headers = {"User-Agent": random.choice(USER_AGENTS)}
                try:
                    async with session.get(
                        url,
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
                        allow_redirects=True,
                    ) as resp:
                        if resp.status == 200:
                            return await resp.text()
                        logger.warning(
                            "[%s] HTTP %d on attempt %d – %s",
                            self.retailer_name,
                            resp.status,
                            attempt,
                            url,
                        )
                except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                    logger.warning(
                        "[%s] Request error on attempt %d: %s",
                        self.retailer_name,
                        attempt,
                        exc,
                    )

                if attempt < MAX_RETRIES:
                    await asyncio.sleep(2**attempt)

            self._cb.record_failure()
            return None
        finally:
            if own_session:
                await session.close()

    # ------------------------------------------------------------------
    # Product helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _is_booster_box(name: str) -> bool:
        lower = name.lower()
        if any(kw in lower for kw in EXCLUSION_KEYWORDS):
            return False
        return any(kw in lower for kw in BOOSTER_BOX_KEYWORDS)

    @staticmethod
    def _categorize(name: str) -> str:
        lower = name.lower()
        if "pokemon" in lower or "pokémon" in lower:
            return "pokemon"
        if "one piece" in lower:
            return "one_piece"
        return "unknown"

    @staticmethod
    def _detect_set(name: str, category: str) -> str:
        sets = POKEMON_SETS if category == "pokemon" else ONE_PIECE_SETS
        lower = name.lower()
        for s in sets:
            if s.lower() in lower:
                return s
        return ""

    @staticmethod
    def _extract_price(text: str) -> float | None:
        m = _PRICE_RE.search(text)
        if m:
            try:
                return float(m.group(1).replace(",", ""))
            except ValueError:
                pass
        return None

    def _build_product(
        self,
        name: str,
        url: str,
        category: str,
        *,
        price: float | None = None,
        in_stock: bool = False,
        image_url: str = "",
    ) -> Product:
        if not url.startswith("http"):
            url = urljoin(self.base_url, url)
        detected_cat = self._categorize(name) if category == "unknown" else category
        return Product(
            name=name.strip(),
            url=url,
            retailer=self.retailer_name,
            in_stock=in_stock,
            price=price,
            category=detected_cat,
            set_name=self._detect_set(name, detected_cat),
            image_url=image_url,
        )
