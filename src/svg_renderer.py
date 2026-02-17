"""Render crossword grid as standalone SVG."""

from __future__ import annotations

from models import CellType, Grid


def render_svg(
    grid: Grid,
    output_path: str,
    show_answers: bool = False,
    cell_size: float | None = None,
) -> None:
    """Write the crossword grid to an SVG file."""
    if cell_size is None:
        cell_size = _default_cell_size(grid.size)

    number_font = _number_font_size(grid.size)
    letter_font = cell_size * 0.45
    grid_dim = cell_size * grid.size

    parts: list[str] = []
    parts.append(
        f'<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{grid_dim}" height="{grid_dim}" '
        f'viewBox="0 0 {grid_dim} {grid_dim}">\n'
    )

    for r in range(grid.size):
        for c in range(grid.size):
            cell = grid.cells[r][c]
            x = c * cell_size
            y = r * cell_size

            if cell.cell_type == CellType.BLACK:
                parts.append(
                    f'  <rect x="{x}" y="{y}" width="{cell_size}" '
                    f'height="{cell_size}" fill="black"/>\n'
                )
            else:
                parts.append(
                    f'  <rect x="{x}" y="{y}" width="{cell_size}" '
                    f'height="{cell_size}" fill="white" '
                    f'stroke="black" stroke-width="0.5"/>\n'
                )

                if cell.number is not None:
                    tx = x + 1.5
                    ty = y + number_font + 1
                    parts.append(
                        f'  <text x="{tx}" y="{ty}" '
                        f'font-family="Helvetica, Arial, sans-serif" '
                        f'font-weight="bold" font-size="{number_font}" '
                        f'fill="black">{cell.number}</text>\n'
                    )

                if show_answers and cell.letter:
                    cx = x + cell_size * 0.55
                    cy = y + cell_size * 0.58
                    parts.append(
                        f'  <text x="{cx}" y="{cy}" '
                        f'text-anchor="middle" dominant-baseline="central" '
                        f'font-family="Helvetica, Arial, sans-serif" '
                        f'font-size="{letter_font}" '
                        f'fill="black">{cell.letter}</text>\n'
                    )

    # Outer border
    parts.append(
        f'  <rect x="0" y="0" width="{grid_dim}" height="{grid_dim}" '
        f'fill="none" stroke="black" stroke-width="1.5"/>\n'
    )
    parts.append('</svg>\n')

    with open(output_path, 'w', encoding='utf-8') as f:
        f.writelines(parts)


def render_puzzle_svg(grid: Grid, output_path: str) -> None:
    """Render puzzle grid (no answers) to SVG."""
    render_svg(grid, output_path, show_answers=False)


def render_answer_svg(grid: Grid, output_path: str) -> None:
    """Render answer grid (with letters) to SVG."""
    render_svg(grid, output_path, show_answers=True)


def _default_cell_size(grid_size: int) -> float:
    if grid_size <= 15:
        return 24.0
    elif grid_size <= 17:
        return 21.0
    else:
        return 17.0


def _number_font_size(grid_size: int) -> float:
    if grid_size <= 13:
        return 8.5
    elif grid_size <= 15:
        return 8.0
    elif grid_size <= 17:
        return 7.0
    else:
        return 6.0
