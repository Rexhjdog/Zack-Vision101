"""Scrapers package."""
from src.scrapers.base import BaseScraper
from src.scrapers.eb_games import EBGamesScraper
from src.scrapers.jb_hifi import JBHiFiScraper
from src.scrapers.target_au import TargetScraper
from src.scrapers.big_w import BigWScraper
from src.scrapers.kmart import KmartScraper

__all__ = [
    'BaseScraper',
    'EBGamesScraper',
    'JBHiFiScraper',
    'TargetScraper',
    'BigWScraper',
    'KmartScraper',
]
