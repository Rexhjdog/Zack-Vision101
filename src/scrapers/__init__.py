"""Retailer scrapers for TCG stock monitoring."""

from src.scrapers.base import BaseScraper
from src.scrapers.big_w import BigWScraper
from src.scrapers.eb_games import EBGamesScraper
from src.scrapers.jb_hifi import JBHiFiScraper
from src.scrapers.kmart import KmartScraper
from src.scrapers.target_au import TargetScraper

SCRAPER_MAP: dict[str, type[BaseScraper]] = {
    "eb_games": EBGamesScraper,
    "jb_hifi": JBHiFiScraper,
    "target_au": TargetScraper,
    "big_w": BigWScraper,
    "kmart": KmartScraper,
}

__all__ = [
    "BaseScraper",
    "BigWScraper",
    "EBGamesScraper",
    "JBHiFiScraper",
    "KmartScraper",
    "TargetScraper",
    "SCRAPER_MAP",
]
