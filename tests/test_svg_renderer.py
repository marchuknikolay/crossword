"""Tests for svg_renderer.py."""

import os
import tempfile
import xml.etree.ElementTree as ET

import pytest

from models import CellType, Direction, Grid, PlacedEntry
from grid_builder import build_grid, number_grid
from svg_renderer import render_svg, render_puzzle_svg, render_answer_svg


def _make_simple_grid():
    """Create a small 5x5 grid with a few words."""
    placed = [
        PlacedEntry(number=1, clue_text="Feline", answer="CAT",
                    row=0, col=0, direction=Direction.ACROSS),
        PlacedEntry(number=2, clue_text="Vehicle", answer="CAR",
                    row=0, col=0, direction=Direction.DOWN),
    ]
    grid = build_grid(placed, 5)
    number_grid(grid)
    return grid


class TestRenderSvg:
    def test_creates_valid_svg(self):
        grid = _make_simple_grid()
        with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as f:
            path = f.name
        try:
            render_svg(grid, path)
            assert os.path.exists(path)
            tree = ET.parse(path)
            root = tree.getroot()
            assert root.tag == "{http://www.w3.org/2000/svg}svg"
        finally:
            os.unlink(path)

    def test_correct_dimensions(self):
        grid = _make_simple_grid()
        with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as f:
            path = f.name
        try:
            render_svg(grid, path, cell_size=24.0)
            tree = ET.parse(path)
            root = tree.getroot()
            expected = str(24.0 * 5)
            assert root.get("width") == expected
            assert root.get("height") == expected
        finally:
            os.unlink(path)

    def test_puzzle_has_no_letters(self):
        grid = _make_simple_grid()
        with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as f:
            path = f.name
        try:
            render_puzzle_svg(grid, path)
            with open(path, 'r') as f:
                content = f.read()
            # Should have number texts but no single-letter texts for answers
            # Numbers are short (1-2 digits), answers are single uppercase letters
            tree = ET.parse(path)
            ns = {"svg": "http://www.w3.org/2000/svg"}
            texts = tree.findall(".//svg:text", ns)
            for t in texts:
                text_content = t.text or ""
                # All text elements should be numbers, not answer letters
                assert text_content.isdigit(), f"Unexpected text: {text_content}"
        finally:
            os.unlink(path)

    def test_answer_has_letters(self):
        grid = _make_simple_grid()
        with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as f:
            path = f.name
        try:
            render_answer_svg(grid, path)
            with open(path, 'r') as f:
                content = f.read()
            # Should contain answer letters
            assert ">C<" in content
            assert ">A<" in content
            assert ">T<" in content
            assert ">R<" in content
        finally:
            os.unlink(path)

    def test_has_black_cells(self):
        grid = _make_simple_grid()
        with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as f:
            path = f.name
        try:
            render_svg(grid, path)
            with open(path, 'r') as f:
                content = f.read()
            assert 'fill="black"' in content
        finally:
            os.unlink(path)

    def test_has_white_cells(self):
        grid = _make_simple_grid()
        with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as f:
            path = f.name
        try:
            render_svg(grid, path)
            with open(path, 'r') as f:
                content = f.read()
            assert 'fill="white"' in content
        finally:
            os.unlink(path)

    def test_has_outer_border(self):
        grid = _make_simple_grid()
        with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as f:
            path = f.name
        try:
            render_svg(grid, path)
            with open(path, 'r') as f:
                content = f.read()
            assert 'stroke-width="1.5"' in content
        finally:
            os.unlink(path)

    def test_has_cell_numbers(self):
        grid = _make_simple_grid()
        with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as f:
            path = f.name
        try:
            render_svg(grid, path)
            tree = ET.parse(path)
            ns = {"svg": "http://www.w3.org/2000/svg"}
            texts = tree.findall(".//svg:text", ns)
            numbers = [t.text for t in texts if t.text and t.text.isdigit()]
            assert "1" in numbers
        finally:
            os.unlink(path)

    def test_custom_cell_size(self):
        grid = _make_simple_grid()
        with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as f:
            path = f.name
        try:
            render_svg(grid, path, cell_size=30.0)
            tree = ET.parse(path)
            root = tree.getroot()
            expected = str(30.0 * 5)
            assert root.get("width") == expected
        finally:
            os.unlink(path)
