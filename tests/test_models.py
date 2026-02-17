"""Tests for models.py."""

import pytest

from models import (
    Cell,
    CellType,
    ClueEntry,
    CrosswordError,
    Direction,
    Grid,
    NumberedClue,
    PlacedEntry,
)


class TestEnums:
    def test_cell_type_values(self):
        assert CellType.BLACK.value == "BLACK"
        assert CellType.WHITE.value == "WHITE"

    def test_direction_values(self):
        assert Direction.ACROSS.value == "ACROSS"
        assert Direction.DOWN.value == "DOWN"


class TestClueEntry:
    def test_creation(self):
        entry = ClueEntry(number=1, clue_text="Feline pet", answer="CAT")
        assert entry.number == 1
        assert entry.clue_text == "Feline pet"
        assert entry.answer == "CAT"

    def test_frozen(self):
        entry = ClueEntry(number=1, clue_text="test", answer="ABC")
        with pytest.raises(AttributeError):
            entry.number = 2


class TestPlacedEntry:
    def test_inherits_clue_entry(self):
        placed = PlacedEntry(
            number=1, clue_text="test", answer="CAT",
            row=3, col=5, direction=Direction.ACROSS,
        )
        assert placed.number == 1
        assert placed.answer == "CAT"
        assert placed.row == 3
        assert placed.col == 5
        assert placed.direction == Direction.ACROSS
        assert isinstance(placed, ClueEntry)

    def test_defaults(self):
        placed = PlacedEntry(number=1, clue_text="test", answer="ABC")
        assert placed.row == 0
        assert placed.col == 0
        assert placed.direction == Direction.ACROSS


class TestCell:
    def test_defaults(self):
        cell = Cell()
        assert cell.cell_type == CellType.BLACK
        assert cell.letter is None
        assert cell.number is None

    def test_mutable(self):
        cell = Cell()
        cell.cell_type = CellType.WHITE
        cell.letter = "A"
        cell.number = 1
        assert cell.cell_type == CellType.WHITE
        assert cell.letter == "A"
        assert cell.number == 1


class TestGrid:
    def test_create(self):
        grid = Grid.create(5)
        assert grid.size == 5
        assert len(grid.cells) == 5
        assert len(grid.cells[0]) == 5

    def test_all_black_initially(self):
        grid = Grid.create(3)
        for r in range(3):
            for c in range(3):
                assert grid.cells[r][c].cell_type == CellType.BLACK

    def test_cells_are_independent(self):
        grid = Grid.create(3)
        grid.cells[0][0].cell_type = CellType.WHITE
        assert grid.cells[0][1].cell_type == CellType.BLACK


class TestNumberedClue:
    def test_creation(self):
        clue = NumberedClue(number=5, clue_text="A clue", answer="WORD", direction=Direction.DOWN)
        assert clue.number == 5
        assert clue.answer == "WORD"
        assert clue.direction == Direction.DOWN


class TestCrosswordError:
    def test_is_exception(self):
        with pytest.raises(CrosswordError, match="test error"):
            raise CrosswordError("test error")
