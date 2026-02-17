"""Build the Grid model from placed entries, assign cell numbers, build clue lists."""

from __future__ import annotations

from models import CellType, Direction, Grid, NumberedClue, PlacedEntry


def build_grid(placed: list[PlacedEntry], grid_size: int) -> Grid:
    """Create a Grid and write letters from each PlacedEntry."""
    grid = Grid.create(grid_size)

    for entry in placed:
        dr = 1 if entry.direction == Direction.DOWN else 0
        dc = 1 if entry.direction == Direction.ACROSS else 0

        for i, letter in enumerate(entry.answer):
            r = entry.row + dr * i
            c = entry.col + dc * i
            cell = grid.cells[r][c]
            cell.cell_type = CellType.WHITE
            if cell.letter is not None and cell.letter != letter:
                raise ValueError(
                    f"Letter conflict at ({r},{c}): existing '{cell.letter}' vs '{letter}'"
                )
            cell.letter = letter

    return grid


def number_grid(grid: Grid) -> None:
    """Scan L→R, T→B and assign sequential numbers where a word starts."""
    counter = 1
    for r in range(grid.size):
        for c in range(grid.size):
            cell = grid.cells[r][c]
            if cell.cell_type != CellType.WHITE:
                continue
            if _starts_across(grid, r, c) or _starts_down(grid, r, c):
                cell.number = counter
                counter += 1


def build_clue_lists(
    grid: Grid, placed: list[PlacedEntry]
) -> tuple[list[NumberedClue], list[NumberedClue]]:
    """Map each PlacedEntry to its grid-assigned number, return sorted across/down lists."""
    across: list[NumberedClue] = []
    down: list[NumberedClue] = []

    for entry in placed:
        cell = grid.cells[entry.row][entry.col]
        if cell.number is None:
            continue
        clue = NumberedClue(
            number=cell.number,
            clue_text=entry.clue_text,
            answer=entry.answer,
            direction=entry.direction,
        )
        if entry.direction == Direction.ACROSS:
            across.append(clue)
        else:
            down.append(clue)

    across.sort(key=lambda c: c.number)
    down.sort(key=lambda c: c.number)
    return across, down


def _starts_across(grid: Grid, r: int, c: int) -> bool:
    """Left is BLACK/edge AND right is WHITE."""
    if grid.cells[r][c].cell_type != CellType.WHITE:
        return False
    left_is_edge_or_black = (c == 0) or (grid.cells[r][c - 1].cell_type == CellType.BLACK)
    right_is_white = (c + 1 < grid.size) and (grid.cells[r][c + 1].cell_type == CellType.WHITE)
    return left_is_edge_or_black and right_is_white


def _starts_down(grid: Grid, r: int, c: int) -> bool:
    """Top is BLACK/edge AND bottom is WHITE."""
    if grid.cells[r][c].cell_type != CellType.WHITE:
        return False
    top_is_edge_or_black = (r == 0) or (grid.cells[r - 1][c].cell_type == CellType.BLACK)
    bottom_is_white = (r + 1 < grid.size) and (grid.cells[r + 1][c].cell_type == CellType.WHITE)
    return top_is_edge_or_black and bottom_is_white
