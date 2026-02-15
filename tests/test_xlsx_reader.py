"""Tests for xlsx_reader.py."""

import pytest

from models import ClueEntry, CrosswordError
from xlsx_reader import _normalize_answer, _validate_and_filter, read_clues

FIXTURES = "tests/fixtures"


class TestReadClues:
    def test_valid_parse(self):
        clues = read_clues(f"{FIXTURES}/small_10.xlsx")
        assert len(clues) > 0
        assert all(isinstance(c, ClueEntry) for c in clues)

    def test_answers_are_uppercase_alpha(self):
        clues = read_clues(f"{FIXTURES}/small_10.xlsx")
        for clue in clues:
            assert clue.answer == clue.answer.upper()
            assert clue.answer.isalpha()

    def test_empty_file_error(self):
        with pytest.raises(CrosswordError):
            read_clues(f"{FIXTURES}/empty.xlsx")

    def test_file_not_found(self):
        with pytest.raises(CrosswordError, match="File not found"):
            read_clues("nonexistent.xlsx")

    def test_dedup_and_short_filter(self, capsys):
        clues = read_clues(f"{FIXTURES}/mixed.xlsx")
        answers = [c.answer for c in clues]
        # HELLO appears once (dedup), HI and NO skipped (too short)
        assert answers.count("HELLO") == 1
        assert "HI" not in answers
        assert "NO" not in answers

    def test_strip_non_alpha(self):
        clues = read_clues(f"{FIXTURES}/mixed.xlsx")
        answers = [c.answer for c in clues]
        assert "WELLKNOWN" in answers
        assert "ICECREAM" in answers


class TestNormalizeAnswer:
    def test_uppercase(self):
        assert _normalize_answer("hello") == "HELLO"

    def test_strip_spaces(self):
        assert _normalize_answer("ice cream") == "ICECREAM"

    def test_strip_hyphens(self):
        assert _normalize_answer("well-known") == "WELLKNOWN"

    def test_strip_special(self):
        assert _normalize_answer("O'Brien") == "OBRIEN"


class TestValidateAndFilter:
    def test_length_filter(self):
        entries = [
            ClueEntry(1, "short", "AB"),
            ClueEntry(2, "ok", "CAT"),
            ClueEntry(3, "long", "A" * 20),
        ]
        result = _validate_and_filter(entries, grid_size=15)
        assert len(result) == 1
        assert result[0].answer == "CAT"

    def test_dedup(self):
        entries = [
            ClueEntry(1, "first", "CAT"),
            ClueEntry(2, "second", "CAT"),
        ]
        result = _validate_and_filter(entries, grid_size=15)
        assert len(result) == 1

    def test_empty_after_filter(self):
        entries = [ClueEntry(1, "short", "AB")]
        with pytest.raises(CrosswordError):
            _validate_and_filter(entries, grid_size=15)
