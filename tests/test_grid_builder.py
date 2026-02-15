"""Tests for grid_builder.py."""

import pytest

from models import CellType, Direction, Grid, NumberedClue, PlacedEntry
from grid_builder import build_grid, number_grid, build_clue_lists, _starts_across, _starts_down


def _make_placed(answer, row, col, direction, number=1):
    return PlacedEntry(
        number=number, clue_text=f"Clue for {answer}", answer=answer,
        row=row, col=col, direction=direction,
    )


class TestBuildGrid:
    def test_basic_across(self):
        placed = [_make_placed("CAT", 0, 0, Direction.ACROSS)]
        grid = build_grid(placed, 5)
        assert grid.cells[0][0].letter == "C"
        assert grid.cells[0][1].letter == "A"
        assert grid.cells[0][2].letter == "T"
        assert grid.cells[0][0].cell_type == CellType.WHITE

    def test_basic_down(self):
        placed = [_make_placed("DOG", 0, 0, Direction.DOWN)]
        grid = build_grid(placed, 5)
        assert grid.cells[0][0].letter == "D"
        assert grid.cells[1][0].letter == "O"
        assert grid.cells[2][0].letter == "G"

    def test_intersection(self):
        placed = [
            _make_placed("CAT", 0, 0, Direction.ACROSS, 1),
            _make_placed("COW", 0, 0, Direction.DOWN, 2),
        ]
        grid = build_grid(placed, 5)
        assert grid.cells[0][0].letter == "C"  # shared

    def test_letter_conflict_raises(self):
        placed = [
            _make_placed("CAT", 0, 0, Direction.ACROSS, 1),
            _make_placed("DOG", 0, 0, Direction.DOWN, 2),  # D != C
        ]
        with pytest.raises(ValueError, match="Letter conflict"):
            build_grid(placed, 5)

    def test_black_cells_remain(self):
        placed = [_make_placed("CAT", 0, 0, Direction.ACROSS)]
        grid = build_grid(placed, 5)
        assert grid.cells[1][0].cell_type == CellType.BLACK


class TestNumberGrid:
    def test_simple_numbering(self):
        placed = [
            _make_placed("CAT", 0, 0, Direction.ACROSS, 1),
            _make_placed("COW", 0, 0, Direction.DOWN, 2),
        ]
        grid = build_grid(placed, 5)
        number_grid(grid)
        assert grid.cells[0][0].number == 1  # starts both across and down

    def test_sequential_numbering(self):
        placed = [
            _make_placed("ABCDE", 0, 0, Direction.ACROSS, 1),
            _make_placed("AXY", 0, 0, Direction.DOWN, 2),
            _make_placed("BPQ", 0, 1, Direction.DOWN, 3),
        ]
        grid = build_grid(placed, 5)
        number_grid(grid)
        assert grid.cells[0][0].number == 1
        assert grid.cells[0][1].number == 2


class TestStartsAcrossDown:
    def test_starts_across_at_edge(self):
        grid = Grid.create(5)
        grid.cells[0][0].cell_type = CellType.WHITE
        grid.cells[0][1].cell_type = CellType.WHITE
        assert _starts_across(grid, 0, 0) is True

    def test_starts_across_after_black(self):
        grid = Grid.create(5)
        # cells[0][0] stays BLACK
        grid.cells[0][1].cell_type = CellType.WHITE
        grid.cells[0][2].cell_type = CellType.WHITE
        assert _starts_across(grid, 0, 1) is True

    def test_not_starts_across_middle(self):
        grid = Grid.create(5)
        grid.cells[0][0].cell_type = CellType.WHITE
        grid.cells[0][1].cell_type = CellType.WHITE
        grid.cells[0][2].cell_type = CellType.WHITE
        assert _starts_across(grid, 0, 1) is False

    def test_starts_down_at_edge(self):
        grid = Grid.create(5)
        grid.cells[0][0].cell_type = CellType.WHITE
        grid.cells[1][0].cell_type = CellType.WHITE
        assert _starts_down(grid, 0, 0) is True

    def test_not_starts_down_middle(self):
        grid = Grid.create(5)
        grid.cells[0][0].cell_type = CellType.WHITE
        grid.cells[1][0].cell_type = CellType.WHITE
        grid.cells[2][0].cell_type = CellType.WHITE
        assert _starts_down(grid, 1, 0) is False


class TestBuildClueLists:
    def test_sorted_by_number(self):
        placed = [
            _make_placed("ABCDE", 0, 0, Direction.ACROSS, 1),
            _make_placed("AXY", 0, 0, Direction.DOWN, 2),
            _make_placed("FGH", 2, 2, Direction.ACROSS, 3),
        ]
        grid = build_grid(placed, 5)
        number_grid(grid)
        across, down = build_clue_lists(grid, placed)

        assert all(isinstance(c, NumberedClue) for c in across)
        assert all(isinstance(c, NumberedClue) for c in down)

        # Across should be sorted by number
        across_nums = [c.number for c in across]
        assert across_nums == sorted(across_nums)

        # Down should be sorted by number
        down_nums = [c.number for c in down]
        assert down_nums == sorted(down_nums)
