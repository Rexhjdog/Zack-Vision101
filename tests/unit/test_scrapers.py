"""Tests for scraper logic (parsing helpers, not live HTTP)."""

from src.scrapers.base import BaseScraper


class TestBoosterBoxDetection:
    """Test the static _is_booster_box filter."""

    def test_detects_booster_box(self):
        assert BaseScraper._is_booster_box("Pokemon TCG Paldean Fates Booster Box")

    def test_detects_booster_display(self):
        assert BaseScraper._is_booster_box("One Piece TCG Booster Display OP-06")

    def test_rejects_sleeve(self):
        assert not BaseScraper._is_booster_box("Pokemon Card Sleeve 65-pack")

    def test_rejects_tin(self):
        assert not BaseScraper._is_booster_box("Pokemon Tin Paldea Partners")

    def test_rejects_playmat(self):
        assert not BaseScraper._is_booster_box("Pokemon Playmat Booster Box Design")

    def test_case_insensitive(self):
        assert BaseScraper._is_booster_box("POKEMON BOOSTER BOX sv05")


class TestCategorize:
    def test_pokemon(self):
        assert BaseScraper._categorize("Pokemon TCG Booster Box") == "pokemon"

    def test_pokemon_accent(self):
        assert BaseScraper._categorize("Pokémon Booster Box") == "pokemon"

    def test_one_piece(self):
        assert BaseScraper._categorize("One Piece TCG Box") == "one_piece"

    def test_unknown(self):
        assert BaseScraper._categorize("Magic The Gathering Box") == "unknown"


class TestDetectSet:
    def test_finds_pokemon_set(self):
        assert (
            BaseScraper._detect_set("Pokemon Paldean Fates Booster Box", "pokemon")
            == "Paldean Fates"
        )

    def test_finds_one_piece_set(self):
        assert (
            BaseScraper._detect_set("One Piece Romance Dawn Booster Box", "one_piece")
            == "Romance Dawn"
        )

    def test_returns_empty_for_unknown(self):
        assert BaseScraper._detect_set("Some Random Product", "pokemon") == ""


class TestExtractPrice:
    def test_normal_price(self):
        assert BaseScraper._extract_price("$89.99") == 89.99

    def test_price_with_comma(self):
        assert BaseScraper._extract_price("$1,299.00") == 1299.00

    def test_price_with_space(self):
        assert BaseScraper._extract_price("$ 45.00") == 45.00

    def test_no_price(self):
        assert BaseScraper._extract_price("Out of stock") is None
