#!/usr/bin/env python3
"""CLI entry point for crossword generation.

Two modes:
  1. XLSX mode (default): read XLSX → place words → build grid → render PDF
  2. Generate mode (--generate): create newspaper-style crossword from built-in word bank
"""

from __future__ import annotations

import argparse
import random
import sys
import time
from pathlib import Path

from models import ClueEntry, CrosswordError, Grid, NumberedClue


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Generate a crossword puzzle PDF."
    )
    p.add_argument("input", nargs="?", default=None,
                   help="Path to XLSX file with clues/answers (not needed with --generate)")
    p.add_argument(
        "output",
        nargs="?",
        default=None,
        help="Output PDF path (default: crossword.pdf or input with .pdf extension)",
    )
    p.add_argument("--generate", action="store_true",
                   help="Generate newspaper-style crossword from built-in word bank")
    p.add_argument("--grid-size", type=int, default=None,
                   help="Grid size NxN (default: 15 for --generate, auto for XLSX)")
    p.add_argument("--title", default="CROSSWORD",
                   help='Title text (default: "CROSSWORD")')
    p.add_argument("--seed", type=int, default=None,
                   help="Random seed (default: random)")
    p.add_argument("--retries", type=int, default=20,
                   help="Placement attempts (default: 20)")
    p.add_argument("--symmetry", action="store_true",
                   help="Enforce 180-degree rotational symmetry (XLSX mode only)")
    return p


def main(argv: list[str] | None = None) -> None:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)

    seed = args.seed if args.seed is not None else random.randint(0, 2**31)
    t0 = time.time()

    try:
        if args.generate:
            _run_generate_mode(args, seed, t0)
        else:
            if args.input is None:
                parser.error("input XLSX file is required (or use --generate)")
            _run_xlsx_mode(args, seed, t0)

    except CrosswordError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def _output_all(
    grid: Grid,
    across: list[NumberedClue],
    down: list[NumberedClue],
    title: str,
    output_path: str,
    unplaced: list[ClueEntry] | None = None,
) -> None:
    """Generate all output files in an 'output' folder: PDF, XLSX, puzzle SVG, answer SVG."""
    from pdf_renderer import render_pdf
    from xlsx_writer import write_clues_xlsx
    from svg_renderer import render_puzzle_svg, render_answer_svg

    stem = Path(output_path).stem
    out_dir = Path(output_path).parent / "output"
    out_dir.mkdir(exist_ok=True)

    pdf_path = str(out_dir / f"{stem}.pdf")
    xlsx_path = str(out_dir / f"{stem}_clues.xlsx")
    puzzle_svg_path = str(out_dir / f"{stem}_puzzle.svg")
    answer_svg_path = str(out_dir / f"{stem}_answer.svg")

    render_pdf(grid, across, down, title, pdf_path)
    write_clues_xlsx(across, down, xlsx_path, unplaced=unplaced)
    render_puzzle_svg(grid, puzzle_svg_path)
    render_answer_svg(grid, answer_svg_path)

    print(f"Output: {pdf_path}", file=sys.stderr)
    print(f"Output: {xlsx_path}", file=sys.stderr)
    print(f"Output: {puzzle_svg_path}", file=sys.stderr)
    print(f"Output: {answer_svg_path}", file=sys.stderr)


def _run_generate_mode(args, seed: int, t0: float) -> None:
    """Generate newspaper-style crossword from built-in word bank."""
    from template_filler import generate_crossword
    from grid_builder import build_grid, build_clue_lists, number_grid

    grid_size = args.grid_size or 15
    output_path = args.output or args.input or "crossword.pdf"

    print(f"Generating {grid_size}x{grid_size} crossword (seed={seed})...",
          file=sys.stderr)

    placed = generate_crossword(
        grid_size=grid_size,
        seed=seed,
        retries=args.retries,
    )

    grid = build_grid(placed, grid_size)
    number_grid(grid)
    across, down = build_clue_lists(grid, placed)

    _output_all(grid, across, down, args.title, output_path)

    elapsed = time.time() - t0
    white_cells = sum(
        1
        for r in range(grid.size)
        for c in range(grid.size)
        if grid.cells[r][c].cell_type.value == "WHITE"
    )
    total_cells = grid.size * grid.size
    density = white_cells / total_cells * 100

    print(
        f"Generated {len(placed)} words, "
        f"grid density {density:.0f}%, "
        f"time {elapsed:.1f}s",
        file=sys.stderr,
    )


def _run_xlsx_mode(args, seed: int, t0: float) -> None:
    """Generate crossword from XLSX word list."""
    from xlsx_reader import read_clues
    from grid_placer import place_words, compute_grid_size
    from grid_builder import build_grid, build_clue_lists, number_grid

    input_path = Path(args.input)
    output_path = args.output or str(input_path.with_suffix(".pdf"))

    grid_size = args.grid_size
    if grid_size is None:
        clues = read_clues(input_path)
        grid_size = compute_grid_size(clues)
        print(f"Auto grid size: {grid_size}x{grid_size}", file=sys.stderr)
    else:
        clues = read_clues(input_path, grid_size)

    print(f"Read {len(clues)} valid clue entries", file=sys.stderr)

    placed = place_words(
        clues,
        grid_size=grid_size,
        seed=seed,
        retries=args.retries,
        symmetry=args.symmetry,
    )

    placed_answers = {p.answer for p in placed}
    unplaced = [c for c in clues if c.answer not in placed_answers]

    grid = build_grid(placed, grid_size)
    number_grid(grid)
    across, down = build_clue_lists(grid, placed)

    _output_all(grid, across, down, args.title, output_path, unplaced=unplaced)

    elapsed = time.time() - t0
    white_cells = sum(
        1
        for r in range(grid.size)
        for c in range(grid.size)
        if grid.cells[r][c].cell_type.value == "WHITE"
    )
    total_cells = grid.size * grid.size
    density = white_cells / total_cells * 100

    print(
        f"Placed {len(placed)}/{len(clues)} words, "
        f"grid density {density:.0f}%, "
        f"time {elapsed:.1f}s",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
