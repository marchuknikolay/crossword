"""Tests for pdf_renderer.py."""

import os
import re
import tempfile

import pytest

from models import CellType, Direction, Grid, NumberedClue
from grid_builder import build_grid, number_grid, build_clue_lists
from models import PlacedEntry
from pdf_renderer import render_pdf, _compute_layout, _adaptive_fit


def _make_placed(answer, row, col, direction, number=1):
    return PlacedEntry(
        number=number, clue_text=f"Clue for {answer}", answer=answer,
        row=row, col=col, direction=direction,
    )


def _make_simple_puzzle():
    """Create a simple 7x7 puzzle for testing."""
    # HELLO across at row 0: H(0,0) E(0,1) L(0,2) L(0,3) O(0,4)
    # HAPPY down at col 0: H(0,0) A(1,0) P(2,0) P(3,0) Y(4,0) — shares H at (0,0)
    # OCEAN down at col 4: O(0,4) C(1,4) E(2,4) A(3,4) N(4,4) — shares O at (0,4)
    placed = [
        _make_placed("HELLO", 0, 0, Direction.ACROSS, 1),
        _make_placed("HAPPY", 0, 0, Direction.DOWN, 2),
        _make_placed("OCEAN", 0, 4, Direction.DOWN, 3),
    ]
    grid = build_grid(placed, 7)
    number_grid(grid)
    across, down = build_clue_lists(grid, placed)
    return grid, across, down


class TestRenderPdf:
    def test_creates_valid_pdf(self):
        grid, across, down = _make_simple_puzzle()
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            path = f.name
        try:
            render_pdf(grid, across, down, "TEST", path)
            assert os.path.exists(path)
            with open(path, "rb") as f:
                header = f.read(8)
                assert header == b"%PDF-1.4"
        finally:
            os.unlink(path)

    def test_two_pages(self):
        grid, across, down = _make_simple_puzzle()
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            path = f.name
        try:
            render_pdf(grid, across, down, "TEST", path)
            with open(path, "rb") as f:
                content = f.read()
                pages = len(re.findall(rb'/Type\s*/Page[^s]', content))
                assert pages == 2
        finally:
            os.unlink(path)

    def test_page_size(self):
        grid, across, down = _make_simple_puzzle()
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            path = f.name
        try:
            render_pdf(grid, across, down, "TEST", path)
            with open(path, "rb") as f:
                content = f.read()
                # ReportLab writes MediaBox with page dimensions
                assert b"612" in content  # width
                assert b"792" in content  # height
        finally:
            os.unlink(path)


class TestComputeLayout:
    def test_default_15x15(self):
        across = [NumberedClue(1, "test", "TEST", Direction.ACROSS)]
        down = [NumberedClue(2, "test", "TEST", Direction.DOWN)]
        layout = _compute_layout(15, across, down, "CROSSWORD")
        assert layout.cell_size == 24.0
        assert layout.grid_size == 15
        assert layout.grid_dim == 360.0

    def test_cell_size_scaling(self):
        across = [NumberedClue(1, "test", "TEST", Direction.ACROSS)]
        down = [NumberedClue(2, "test", "TEST", Direction.DOWN)]

        layout_13 = _compute_layout(13, across, down, "TEST")
        assert layout_13.cell_size == 24.0

        layout_17 = _compute_layout(17, across, down, "TEST")
        assert layout_17.cell_size == 21.0

        layout_21 = _compute_layout(21, across, down, "TEST")
        assert layout_21.cell_size == 17.0


class TestAdaptiveFit:
    def test_no_change_when_fits(self):
        across = [NumberedClue(1, "Short clue", "TEST", Direction.ACROSS)]
        down = [NumberedClue(2, "Short clue", "TEST", Direction.DOWN)]
        layout = _compute_layout(15, across, down, "TEST")
        original_font = layout.clue_font_size
        layout = _adaptive_fit(across, down, layout)
        assert layout.clue_font_size == original_font
