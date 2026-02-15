# Design: Crossword Puzzle PDF Generator

## Status: FINAL

---

## Context

Greenfield Python 3.10+ CLI tool. Reads XLSX word list (Number, Clue, Answer), auto-places words into a 15x15 crossword grid via greedy algorithm, generates print-ready newspaper-style PDF (US Letter). Reference layout: photo_2026-02-11_22-17-07.jpg.

---

## All Decisions

| Decision | Choice |
|----------|--------|
| Python | 3.10+ |
| Input | 3-column only (Number, Clue, Answer); XLSX numbers are ordering hints, discarded after placement |
| Grid | 15x15 default, mutable (in-place modification) |
| Words | ~60-70 target; error if best attempt < 30 |
| Algorithm | Greedy + retry (20 attempts); first word dead-center |
| Symmetry | Optional --symmetry flag (increases retries to 40) |
| Scoring | 2*intersections + centrality - expansion + jitter(0..0.1) |
| Errors | Warnings to stderr inline; fatal errors collected, raised as CrosswordError |
| PlacedEntry | Inherits from ClueEntry (dataclass inheritance) |
| PDF | Canvas (grid) + Platypus Paragraphs (clues); Helvetica family |
| Adaptive fit | Pre-measure via Paragraph.wrap(), then adjust layout params |
| DOWN columns | Pre-measure heights, greedy-assign to shortest column |
| Answer key | Grid only with filled letters (page 2), no clues |

---

## Pipeline

```
input.xlsx → xlsx_reader → grid_placer → grid_builder → pdf_renderer → output.pdf
               │               │               │               │
          ClueEntry[]    PlacedEntry[]    Grid + clues      2-page PDF
```

---

## Entity Design

### Enums

| Enum | Values | Module |
|------|--------|--------|
| CellType | BLACK, WHITE | models.py |
| Direction | ACROSS, DOWN | models.py |

### Data Classes

| Class | Mutable | Attributes | Notes |
|-------|---------|------------|-------|
| ClueEntry | frozen | number (int), clue_text (str), answer (str) | answer: uppercase, alpha-only |
| PlacedEntry(ClueEntry) | frozen | row (int), col (int), direction (Direction) | inherits ClueEntry fields |
| Cell | mutable | cell_type (CellType=BLACK), letter (str?=None), number (int?=None) | |
| Grid | mutable | size (int), cells (list[list[Cell]]) | factory: Grid.create(size) → all-BLACK |
| NumberedClue | frozen | number (int), clue_text (str), direction (Direction) | display number from grid position |

### Entity Relationships

```
ClueEntry ──[place]──► PlacedEntry ──[build]──► Grid (cells with letters)
                                                  │
PlacedEntry + Grid ──[number]──► NumberedClue (grid-assigned number + clue text)
```

- ClueEntry 1:0..1 PlacedEntry (some words may be skipped by placer)
- PlacedEntry N:1 Grid
- Grid 1:N Cell
- PlacedEntry + Grid → NumberedClue

---

## Component Diagram

```
┌──────────────────────────────────────────────────────────────┐
│                  crossword_generator.py                       │
│  CLI: input, [output], --grid-size, --title, --seed,         │
│       --symmetry, --retries                                   │
└──────┬──────────┬──────────┬──────────┬──────────────────────┘
       │          │          │          │
       ▼          ▼          ▼          ▼
┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐
│xlsx_reader│ │grid_placer│ │grid_build│ │pdf_renderer  │
│          │ │          │ │          │ │              │
│read_clues│►│place_words│►│build_grid│►│render_pdf    │
│          │ │          │ │number    │ │              │
│ openpyxl │ │ random   │ │clue_lists│ │ reportlab    │
└──────────┘ └──────────┘ └──────────┘ └──────────────┘
       └──────────┴──────────┴──────────────────┘
                         │
                         ▼
             ┌─────────────────────┐
             │     models.py       │
             │  all data classes   │
             └─────────────────────┘
```

---

## Implementation Dependency Graph

```
Level 0:  models.py                    (stdlib only)
Level 1:  xlsx_reader.py              (models + openpyxl)
Level 2:  grid_placer.py              (models + random)
Level 3:  grid_builder.py             (models only)
Level 4:  pdf_renderer.py             (models + reportlab)
Level 5:  crossword_generator.py      (all above + argparse)
```

Levels 1-4 depend only on models.py (star). Pipeline data flow is sequential. Each level independently testable.

---

## Module Internals

### xlsx_reader.py

| Function | Signature | Responsibility |
|----------|-----------|----------------|
| read_clues | (path, grid_size) → list[ClueEntry] | Main: open workbook, detect header, parse, validate |
| _detect_header_row | (sheet) → int | First row where col A parses as int |
| _normalize_answer | (raw) → str | Uppercase, strip non-alpha |
| _validate_and_filter | (entries, grid_size) → list[ClueEntry] | Length 3..grid_size, deduplicate (warn), error if 0 remain |

### grid_placer.py

**Internal types** (not in models.py): WorkingGrid = 2D list[list[str?]], Candidate = namedtuple(row, col, direction, intersections)

| Function | Signature | Responsibility |
|----------|-----------|----------------|
| place_words | (clues, grid_size, seed, retries, symmetry) → list[PlacedEntry] | Retry loop: N attempts, pick best; error if best < 30 words |
| _single_attempt | (clues, grid_size, rng, symmetry) → (placed, stats) | Sort by length desc, place first at dead center, greedy iterate |
| _find_candidates | (answer, working_grid, placed, grid_size, symmetry) → list[Candidate] | All valid positions intersecting existing words |
| _score_candidate | (candidate, working_grid, grid_size) → float | 2*intersections + centrality - expansion + jitter |
| _is_valid_placement | (answer, row, col, dir, working_grid, grid_size, symmetry) → bool | Bounds + letter match + no extension + no 2-letter perp + symmetry |
| _place_on_grid | (answer, row, col, dir, working_grid) → None | Write letters |
| _compare_attempts | (a, b) → better | By: word count → intersections → compactness |

**Scoring**: centrality = negative normalized Manhattan distance from word midpoint to grid center. Expansion = penalty for extending beyond current bounding box. Compactness = white_cells / bounding_box_area.

**Symmetry mode**: cell(r,c) and cell(N-1-r, N-1-c) must share type. On placement, mark symmetric partners as WHITE-reserved. Increase default retries to 40.

### grid_builder.py

| Function | Signature | Responsibility |
|----------|-----------|----------------|
| build_grid | (placed, grid_size) → Grid | Create Grid, write letters from PlacedEntry list |
| number_grid | (grid) → None | In-place: scan L→R T→B, assign sequential numbers where starts_across or starts_down |
| build_clue_lists | (grid, placed) → (across: list[NumberedClue], down: list[NumberedClue]) | Look up grid-assigned number for each PlacedEntry, sort by number |
| _starts_across | (grid, r, c) → bool | Left=BLACK/edge AND right=WHITE |
| _starts_down | (grid, r, c) → bool | Top=BLACK/edge AND bottom=WHITE |

### pdf_renderer.py

**LayoutParams** (internal): page 612x792, margin 36, cell_size 24 (15x15), grid right-aligned, across ~168pt wide left of grid, down 3 columns 12pt gutters, clue font 7.5pt, leading 9pt, space_after 1.5pt, number font 6pt.

| Function | Signature | Responsibility |
|----------|-----------|----------------|
| render_pdf | (grid, across, down, title, output_path) → None | Compute layout, adaptive fit, draw page 1 + page 2 |
| _compute_layout | (grid_size, across, down) → LayoutParams | All positions and sizes |
| _adaptive_fit | (across, down, layout) → LayoutParams | Pre-measure Paragraphs; step sequence until fits |
| _draw_title_banner | (canvas, layout) → y_below | Black rect + white centered bold 16pt |
| _draw_grid | (canvas, grid, layout, show_answers) → None | BLACK=solid fill, WHITE=stroke, numbers upper-left, optional letters, 1.5pt outer border |
| _draw_across_zone | (canvas, across, layout) → None | Section header + single clue column |
| _draw_down_zone | (canvas, down, layout) → None | Section header + multi-column, height-balanced via pre-measure greedy-assign to shortest |
| _draw_section_header | (canvas, text, x, y, width) → y_below | Black rect + white bold 9pt |
| _draw_clue_column | (canvas, clues, x, y, width, layout) → y_bottom | Render Paragraphs: bold number + clue text |

**Adaptive fitting sequence**: reduce font 0.5pt (min 6) → reduce space_after to 0.5 → 4 columns → reduce cell_size 1pt (min 16) → overflow to page 2 (answer key → page 3).

**DOWN column balancing**: pre-measure each clue Paragraph height via wrap(), greedy-assign each clue to the column with shortest current total height.

### crossword_generator.py

| Function | Responsibility |
|----------|----------------|
| main | argparse, orchestrate read→place→build→render, print summary, handle errors |
| _build_arg_parser | Define CLI args with defaults: grid-size=15, title="CROSSWORD", seed=random, retries=20 |

Summary: "Placed X/Y words, grid density Z%, time Ns"

---

## PDF Layout

```
┌────────────────────────────────────┐
│         TITLE BANNER (28pt)        │  Black rect, white Helvetica-Bold 16pt centered
├──────────────┬─────────────────────┤
│  ACROSS      │                     │
│  header bar  │      GRID           │  Grid: right-aligned, 24pt cells
│  1. Clue     │    (NxN)           │  Across: single column left of grid
│  5. Clue     │                     │  Clue: "<b>N.</b> text" Helvetica 7.5pt
│  ...         │                     │
├──────────────┴─────────────────────┤
│  DOWN header bar                   │
│  col1        │  col2      │  col3  │  3 columns, height-balanced
│  ...         │  ...       │  ...   │  12pt gutters
└────────────────────────────────────┘

Page 2: "ANSWER KEY" banner + grid with letters (bold, centered, ~60% cell), no clues
```

---

## Testing Strategy

| Test file | Key test cases |
|-----------|---------------|
| test_models.py | Dataclass creation, Grid.create factory, enum values |
| test_xlsx_reader.py | Valid parse, header detection, normalization, length filter, dedup warning, empty-file error |
| test_grid_placer.py | Determinism (same seed → same result), adjacency rejection, bounds, symmetry validation, retry best-of, min 30 word threshold error, min 45 words on real input (@slow) |
| test_grid_builder.py | Numbering sequence, starts_across/down edge cases, clue list sorting, letter conflict detection |
| test_pdf_renderer.py | Valid PDF header, 2-page count, page size 612x792, text contains "ACROSS"/"DOWN"/"ANSWER KEY", adaptive fitting triggers |
| test_integration.py | End-to-end: xlsx → pdf, verify file exists and valid (@slow) |

Fixtures: small 5-10 entry XLSX files in tests/fixtures/. Fast suite < 2s, full < 30s.

---

## Implementation Order

| Step | Module | Test file | Depends on |
|------|--------|-----------|------------|
| 1 | models.py | test_models.py | — |
| 2 | xlsx_reader.py | test_xlsx_reader.py | Step 1 |
| 3 | grid_placer.py | test_grid_placer.py | Step 1 |
| 4 | grid_builder.py | test_grid_builder.py | Step 1 |
| 5 | pdf_renderer.py | test_pdf_renderer.py | Step 1 |
| 6 | crossword_generator.py | test_integration.py | Steps 1-5 |
| 7 | requirements.txt | — | — |

Each step: implement module + its test file before moving to next.

---

## File Structure

```
cross2/
    crossword_generator.py
    models.py
    xlsx_reader.py
    grid_placer.py
    grid_builder.py
    pdf_renderer.py
    requirements.txt          # openpyxl>=3.1.0, reportlab>=4.0
    tests/
        test_models.py
        test_xlsx_reader.py
        test_grid_placer.py
        test_grid_builder.py
        test_pdf_renderer.py
        test_integration.py
        fixtures/
    docs/
        SPECIFICATION.md
        design_crossword_generator.md
```

---

## Verification

1. Run: `python crossword_generator.py input_example.xlsx output.pdf`
2. Open PDF, visually verify against reference photo: grid, numbering, clues, layout
3. Run: `python crossword_generator.py input_example.xlsx symmetric.pdf --symmetry`
4. Verify 180-degree rotational symmetry
5. Run: `pytest` — all pass
6. Run: `pytest -m "not slow"` — under 2s
