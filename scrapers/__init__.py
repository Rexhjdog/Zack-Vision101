# Scraper package
from scrapers.base import BaseScraper
from scrapers.eb_games import EBGamesScraper
from scrapers.jb_hifi import JBHiFiScraper
from scrapers.target_au import TargetScraper
from scrapers.big_w import BigWScraper
from scrapers.kmart import KmartScraper

__all__ = [
    'BaseScraper',
    'EBGamesScraper',
    'JBHiFiScraper',
    'TargetScraper',
    'BigWScraper',
    'KmartScraper',
]
