"""Tests for grid_placer.py."""

import pytest

from models import ClueEntry, CrosswordError, Direction, PlacedEntry
from grid_placer import place_words, _single_attempt, _is_valid_placement

import random


_LARGE_WORD_LIST = [
    "ELEPHANT", "PRACTICE", "LAUGHTER", "HONESTY", "SILENCE",
    "ACTIONS", "REVENGE", "JUPITER", "BANANA", "MONKEY",
    "ORANGE", "PURPLE", "CASTLE", "BRIDGE", "FOREST",
    "GARDEN", "SUMMER", "WINTER", "SPRING", "PLANET",
    "ROCKET", "GUITAR", "VIOLIN", "FLUTES", "CAMERA",
    "LAPTOP", "MOBILE", "DESIGN", "MARKET", "COFFEE",
    "BREADS", "CHEESE", "SALMON", "TOMATO", "ONIONS",
    "GRAPES", "CHERRY", "MANGOS", "PEACHY", "TRAINS",
    "OCEANS", "PIANOS", "ANIMAL", "BASKET", "CANDLE",
    "DESERT", "ENERGY", "FABRIC", "GALAXY", "HAMMER",
    "ISLAND", "JACKET", "MATRIX", "NEEDLE", "ORIGIN",
    "PALACE", "QUARTZ", "RIBBON", "SILVER", "TURBAN",
    "MUSEUM", "NATURE", "OPTION", "PENCIL", "HARBOR",
    "TRAVEL", "UNIQUE", "VALLEY", "WONDER", "YELLOW",
    "ZENITH", "ANCHOR", "BONFIRE", "CRYSTAL", "DOLPHIN",
    "EMERALD", "FORTUNE", "GLIMPSE", "JOURNEY", "KITCHEN",
    "LANTERN", "MONSTER", "NEPTUNE", "PANTHER", "QUARREL",
    "RAINBOW", "SPARROW", "TRUMPET", "UNICORN", "VENTURE",
    "WHISPER", "EXPRESS", "ZEALOUS", "ABALONE", "SURFACE",
    "SHELTER", "MINERAL", "CLIMATE", "TEXTILE", "ROUTINE",
]


def _make_clues(words: list[str]) -> list[ClueEntry]:
    """Helper to create ClueEntry list from word strings."""
    return [ClueEntry(i + 1, f"Clue for {w}", w) for i, w in enumerate(words)]


class TestPlaceWords:
    def test_determinism(self):
        """Same seed produces same single-attempt result."""
        clues = _make_clues(_LARGE_WORD_LIST)
        rng1 = random.Random(123)
        rng2 = random.Random(123)
        result1, _ = _single_attempt(clues, 15, rng1, False)
        result2, _ = _single_attempt(clues, 15, rng2, False)

        assert len(result1) == len(result2)
        for a, b in zip(result1, result2):
            assert a.answer == b.answer
            assert a.row == b.row
            assert a.col == b.col
            assert a.direction == b.direction

    def test_minimum_threshold(self):
        """Too few words should raise CrosswordError."""
        clues = _make_clues(["CAT", "DOG", "FOX"])
        with pytest.raises(CrosswordError, match="minimum 30"):
            place_words(clues, grid_size=15, seed=42, retries=5)

    def test_placed_entries_are_valid(self):
        """All placed entries from a single attempt should be PlacedEntry instances."""
        clues = _make_clues(_LARGE_WORD_LIST)
        rng = random.Random(42)
        result, _ = _single_attempt(clues, 15, rng, False)
        assert len(result) >= 10
        for entry in result:
            assert isinstance(entry, PlacedEntry)
            assert entry.direction in (Direction.ACROSS, Direction.DOWN)
            assert 0 <= entry.row < 15
            assert 0 <= entry.col < 15

    @pytest.mark.slow
    def test_real_input_places_30_plus(self):
        """With real input, should place at least 30 words."""
        from xlsx_reader import read_clues
        clues = read_clues("input_example.xlsx")
        result = place_words(clues, grid_size=15, seed=42, retries=30)
        assert len(result) >= 30


class TestSingleAttempt:
    def test_first_word_at_center(self):
        words = ["CROSSWORD", "ACROSS", "DOWN", "CLUE", "GRID"]
        clues = _make_clues(words)
        rng = random.Random(42)
        placed, stats = _single_attempt(clues, 15, rng, False)
        # First placed word should be near center
        first = placed[0]
        assert first.row == 7  # 15 // 2
        assert first.direction == Direction.ACROSS

    def test_returns_stats(self):
        words = ["HELLO", "WORLD", "EARTH", "HEART"]
        clues = _make_clues(words)
        rng = random.Random(42)
        _, stats = _single_attempt(clues, 15, rng, False)
        assert "word_count" in stats
        assert "intersections" in stats
        assert "compactness" in stats
        assert stats["word_count"] >= 1


class TestIsValidPlacement:
    def test_out_of_bounds(self):
        working = [[None] * 10 for _ in range(10)]
        # HELLO (5 chars) at col 8 in a 10-wide grid would end at col 12 — out of bounds
        # But _is_valid_placement relies on caller for bounds, so test via _find_candidates
        from grid_placer import _find_candidates
        # Place a letter to enable intersection-based search
        working[0][0] = "H"
        candidates = _find_candidates("HELLO", working, 5, False, set())
        # No candidate should be out of bounds
        for c in candidates:
            assert c.row >= 0 and c.col >= 0

    def test_letter_conflict(self):
        working = [[None] * 5 for _ in range(5)]
        working[0][0] = "X"
        assert not _is_valid_placement("HELLO", 0, 0, Direction.ACROSS, working, 5, False, set())

    def test_letter_match(self):
        working = [[None] * 10 for _ in range(10)]
        working[0][0] = "H"
        assert _is_valid_placement("HELLO", 0, 0, Direction.ACROSS, working, 10, False, set())

    def test_no_extension(self):
        """Should not extend an existing word."""
        working = [[None] * 10 for _ in range(10)]
        working[0][3] = "X"  # Letter right after where HELLO would end
        # HELLO at (0,0) would end at col 4, but col 3 has a letter before position 3
        # Actually HELLO is 5 chars at (0,0) -> cols 0-4. Col 3 has X which is 'L'!='X'
        # Let me make a clearer test
        working2 = [[None] * 10 for _ in range(10)]
        working2[0][5] = "X"  # Letter right after HELLO ends (col 0-4)
        assert not _is_valid_placement("HELLO", 0, 0, Direction.ACROSS, working2, 10, False, set())
