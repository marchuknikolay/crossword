# Crossword Puzzle PDF Generator - Specification

## Context

Build a Python CLI tool that reads an XLSX file containing crossword clues/answers and generates a print-ready PDF crossword puzzle. The output should match newspaper-style crossword layout: title banner at top, grid on the right, ACROSS clues on the left, DOWN clues in columns below.

---

## 1. XLSX Input Format

Single worksheet (first/active sheet) with header row + data rows:

| Column | Header      | Type    | Description                                              | Example        |
|--------|-------------|---------|----------------------------------------------------------|----------------|
| A      | `Number`    | Integer | Clue number matching the cell number in grid             | `1`            |
| B      | `Direction` | String  | `A` for Across, `D` for Down                             | `A`            |
| C      | `Row`       | Integer | 1-based row of first letter (1 = top)                    | `1`            |
| D      | `Col`       | Integer | 1-based column of first letter (1 = left)                | `1`            |
| E      | `Clue`      | String  | Clue text shown to solver                                | `"Feline pet"` |
| F      | `Answer`    | String  | Answer word (uppercase), length determines cell span      | `"CAT"`        |

**Optional `Meta` sheet** (key-value pairs):

| Key        | Default              |
|------------|----------------------|
| `Title`    | `"CROSSWORD"`        |
| `GridSize` | Auto-derived from data |

**Validation rules:**
- Each `(Number, Direction)` pair must be unique
- Answers must contain only A-Z (strip spaces/hyphens)
- Answers must fit within grid bounds
- Overlapping cells must have matching letters
- Warn (don't error) if XLSX numbers don't match auto-derived numbering

---

## 2. Grid Generation Algorithm

1. **Initialize** NxN grid of BLACK cells (0-indexed internally, 1-indexed in XLSX)
2. **Place answers**: For each entry, mark covered cells as WHITE and assign letters. Detect letter conflicts.
3. **Assign cell numbers**: Scan left-to-right, top-to-bottom. A white cell gets a number if it starts an Across word (left neighbor is black/edge AND right neighbor is white) OR starts a Down word (top neighbor is black/edge AND bottom neighbor is white). Increment counter sequentially.
4. **Optional symmetry check**: Warn if grid lacks 180-degree rotational symmetry.

---

## 3. PDF Layout (US Letter, 612x792 pt)

```
+----------------------------------------------------------+
|                     [TITLE BANNER]                        |  Zone A: 28pt tall
|                                                           |
|  +------------------+   +-----------------------------+   |
|  |  ACROSS header   |   |                             |   |
|  |  1. Clue text    |   |         GRID                |   |  Zone B: grid + across
|  |  5. Clue text    |   |       (NxN cells)           |   |
|  |  ...             |   |                             |   |
|  +------------------+   +-----------------------------+   |
|                                                           |
|  +------------------------------------------------------+ |
|  |  DOWN header                                         | |  Zone C: down clues
|  |  col1          |  col2          |  col3              | |  (3 columns)
|  +------------------------------------------------------+ |
+----------------------------------------------------------+
```

**Margins:** 36pt (0.5") all sides. Usable: 540x720 pt.

### Zone A - Title Banner
- Black-filled rect, full usable width, 28pt tall
- White centered text: Helvetica-Bold 16pt

### Zone B - Grid + Across Clues (side by side)
- **Grid** (right side): cell_size=24pt for 15x15 (360x360pt), right-aligned to right margin
- **Across clues** (left side): single column in space left of grid (~168pt wide), starts at same Y as grid top

### Zone C - Down Clues (below grid)
- 14pt gap below grid/across bottom
- 3 columns with 12pt gutters, each ~172pt wide
- Clues distributed across columns for balanced height

### Cell rendering
- **BLACK cell**: solid black filled rect
- **WHITE cell**: white fill, black stroke (0.5pt line width)
- **Cell number**: Helvetica 6pt, positioned 1.5pt from left edge, 1pt from top edge
- **Grid outer border**: 1.5pt stroke around entire grid

### Clue rendering
- **Section headers** (ACROSS/DOWN): black rect with white Helvetica-Bold 9pt text
- **Clue text**: `<b>N.</b> clue text` using ReportLab Paragraph for auto-wrapping
- **Clue style**: Helvetica 7.5pt, leading 9pt, spaceAfter 1.5pt

### Page 2 - Answer Key
- Same grid position and size as page 1
- All white cells filled with answer letters (Helvetica-Bold, centered, ~60% of cell_size)
- Cell numbers still shown (smaller, upper-left)
- Title: "ANSWER KEY" banner (same style as page 1 title)
- No clue sections on this page

### Adaptive fitting (if content overflows page 1)
1. Reduce clue font size by 0.5pt (min 6pt)
2. Reduce spaceAfter to 0.5pt
3. Increase DOWN columns from 3 to 4
4. Reduce cell_size by 1pt (min 16pt)
5. Last resort: overflow to second page (answer key moves to page 3)

### Cell size scaling by grid size
| Grid Size | Cell Size | Number Font | Grid Dimension |
|-----------|-----------|-------------|----------------|
| 13x13     | 24pt      | 6.5pt       | 312x312pt      |
| 15x15     | 24pt      | 6pt         | 360x360pt      |
| 17x17     | 21pt      | 5.5pt       | 357x357pt      |
| 21x21     | 17pt      | 5pt         | 357x357pt      |

---

## 4. Project Structure

```
cross2/
    crossword_generator.py   # CLI entry point: python crossword_generator.py input.xlsx [output.pdf]
    models.py                # Data classes: CellType, Cell, Grid, ClueEntry
    xlsx_reader.py           # XLSX parsing + validation (openpyxl)
    grid_builder.py          # Grid construction, letter placement, numbering
    pdf_renderer.py          # ReportLab PDF layout + rendering + adaptive fitting
    requirements.txt         # openpyxl>=3.1.0, reportlab>=4.0
```

### CLI interface
```
python crossword_generator.py input.xlsx [output.pdf]
```
If output not specified, uses input filename with `.pdf` extension.

---

## 5. Implementation Order

1. **`models.py`** - CellType enum, Cell dataclass, Grid dataclass
2. **`xlsx_reader.py`** - `read_clues()` and `validate_clues()` functions
3. **`grid_builder.py`** - `build_grid()`, cell numbering, `build_clue_lists()`
4. **`pdf_renderer.py`** - Layout computation, grid drawing, clue rendering, adaptive fitting
5. **`crossword_generator.py`** - CLI orchestration
6. **`requirements.txt`** - Dependencies

---

## 6. Edge Cases

- **Long clue text**: auto-wraps via Paragraph Paragraph flowable
- **Empty clue text**: render just bold number
- **Answers with spaces/hyphens**: strip non-alpha before placing
- **Small puzzles (<20 clues)**: reduce DOWN columns to 2
- **XML-special chars in clues** (`<`, `>`, `&`): escape with `xml.sax.saxutils.escape()`
- **Grid size**: square only (NxN), auto-derived from data or specified in Meta sheet

---

## 7. Verification

1. Create a sample XLSX with the Crossword #2 data from the reference image
2. Run `python crossword_generator.py sample.xlsx sample.pdf`
3. Open PDF and visually compare against the reference image
4. Verify: grid dimensions, black cell placement, numbering, clue text accuracy, layout proportions
5. Test with 13x13 and 21x21 grids to confirm adaptive layout works
