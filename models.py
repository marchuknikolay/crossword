"""Data models for the crossword generator."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class CellType(Enum):
    BLACK = "BLACK"
    WHITE = "WHITE"


class Direction(Enum):
    ACROSS = "ACROSS"
    DOWN = "DOWN"


@dataclass(frozen=True)
class ClueEntry:
    """A clue/answer pair read from XLSX. ``number`` is an ordering hint only."""

    number: int
    clue_text: str
    answer: str  # uppercase, alpha-only


@dataclass(frozen=True)
class PlacedEntry(ClueEntry):
    """A ClueEntry that has been assigned a position on the grid."""

    row: int = 0
    col: int = 0
    direction: Direction = Direction.ACROSS


@dataclass
class Cell:
    """A single cell in the crossword grid."""

    cell_type: CellType = CellType.BLACK
    letter: str | None = None
    number: int | None = None


@dataclass
class Grid:
    """An NxN crossword grid of Cell objects."""

    size: int
    cells: list[list[Cell]] = field(default_factory=list)

    @classmethod
    def create(cls, size: int) -> Grid:
        """Create a grid of all-BLACK cells."""
        cells = [[Cell() for _ in range(size)] for _ in range(size)]
        return cls(size=size, cells=cells)


@dataclass(frozen=True)
class NumberedClue:
    """A clue with its grid-assigned display number."""

    number: int
    clue_text: str
    direction: Direction


class CrosswordError(Exception):
    """Fatal error during crossword generation."""
