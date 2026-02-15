# Crossword Generator

A Python tool that generates newspaper-style crossword puzzles and renders them as single-page PDFs.

## Setup

**Requirements:** Python 3.11+

Install dependencies:

```bash
pip install openpyxl reportlab blacksquare nltk
```

Download NLTK data (needed for auto-clue generation):

```python
python3 -c "import nltk; nltk.download('wordnet'); nltk.download('omw-1.4')"
```

## Usage

### Generate mode (built-in word bank)

Generate a newspaper-style 15x15 crossword with 180-degree rotational symmetry:

```bash
python3 crossword_generator.py --generate
```

Options:

```bash
python3 crossword_generator.py --generate --seed 42          # reproducible output
python3 crossword_generator.py --generate --retries 30       # more fill attempts
python3 crossword_generator.py --generate --title "MY PUZZLE" # custom title
python3 crossword_generator.py --generate output.pdf          # custom output path
```

### XLSX mode (custom words)

Provide your own words and clues in an Excel file:

```bash
python3 crossword_generator.py input_example.xlsx
python3 crossword_generator.py input_example.xlsx output.pdf --grid-size 15 --symmetry
```

The XLSX file should have two columns: **word** and **clue** (first row is treated as a header).

### All CLI options

| Flag | Description | Default |
|------|-------------|---------|
| `input` | Path to XLSX file (not needed with `--generate`) | - |
| `output` | Output PDF path | `crossword.pdf` or `<input>.pdf` |
| `--generate` | Use built-in word bank instead of XLSX | off |
| `--grid-size N` | Grid size NxN | 15 (generate) / auto (XLSX) |
| `--title TEXT` | Title displayed on the PDF | `CROSSWORD` |
| `--seed N` | Random seed for reproducibility | random |
| `--retries N` | Number of fill attempts | 20 |
| `--symmetry` | Enforce 180-degree rotational symmetry (XLSX only) | off |

## How It Works

The generator follows a five-stage pipeline:

### 1. Template Generation

Creates a 15x15 boolean grid of black and white cells with 180-degree rotational symmetry (standard American crossword property). Validates that all white cells are connected and no word slots are shorter than 3 letters.

### 2. Word List Construction

Merges two word sources into a scored list:

- **Word bank** (~3,600 curated words with hand-written clues, score 1.0)
- **Blacksquare dictionary** (~304K words, filtered through `/usr/share/dict/words`, score 0.3)

Every word is pre-filtered to guarantee a clue exists via the word bank, inflection derivation, or WordNet. This reduces the dictionary to ~55K words but ensures zero unclueable entries.

### 3. Grid Filling

Passes the template and word list to blacksquare's DFS solver, which fills every slot using depth-first search with backtracking. Higher-scored bank words are preferred. If filling fails, a new template is generated and retried.

### 4. Clue Lookup

For each placed word, a clue is resolved in priority order:

1. **Word bank** -- direct lookup
2. **Inflection derivation** -- strips suffixes (-S, -ED, -ING, -ER, -LY) to find a base word in the bank
3. **WordNet** -- shortest primary-sense definition, cleaned and truncated to 35 characters

### 5. PDF Rendering

Uses ReportLab to produce a single-page PDF. The grid is centered at the top, with all clues (across and down) laid out in balanced multi-column format below. An adaptive fitting algorithm adjusts font size, spacing, column count, and cell size until everything fits on one page.

## Testing

```bash
pytest                      # unit tests only
pytest -m slow              # integration tests (generates full PDFs)
pytest -m "not slow"        # skip slow tests
```

## Project Structure

```
crossword_generator.py   # CLI entry point, argument parsing
template_filler.py       # Template generation, blacksquare filling, clue lookup
grid_placer.py           # XLSX mode word placement (greedy + simulated annealing)
pdf_renderer.py          # PDF layout and rendering (ReportLab)
grid_builder.py          # Converts placed words into numbered grid
models.py                # Data models (Grid, Cell, PlacedEntry, ClueEntry, etc.)
word_bank.py             # Hand-curated word/clue pairs (~3,600 entries)
xlsx_reader.py           # XLSX file parser
input_example.xlsx       # Example input file
tests/                   # Unit and integration tests
```
