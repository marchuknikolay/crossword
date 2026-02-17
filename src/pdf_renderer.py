"""Render crossword puzzle to a newspaper-style PDF using ReportLab.

Layout: grid centered at top, all clues (across + down) in multi-column
format below the grid, matching real newspaper crossword style.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from xml.sax.saxutils import escape

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.platypus import Paragraph

from models import CellType, Direction, Grid, NumberedClue

PAGE_W, PAGE_H = letter  # 612 x 792
MARGIN = 36


@dataclass
class LayoutParams:
    """All computed layout measurements."""

    page_w: float = PAGE_W
    page_h: float = PAGE_H
    margin: float = MARGIN
    usable_w: float = PAGE_W - 2 * MARGIN
    usable_h: float = PAGE_H - 2 * MARGIN

    # Grid
    grid_size: int = 15
    cell_size: float = 24.0
    grid_dim: float = 0.0
    grid_x: float = 0.0
    grid_y: float = 0.0  # top of grid in page coords

    # Title banner
    banner_h: float = 28.0
    banner_y: float = 0.0

    # Fonts
    clue_font_size: float = 9.0
    clue_leading: float = 10.5
    space_after: float = 1.5
    number_font_size: float = 6.0

    # Clue zone (all clues below grid)
    clue_zone_y: float = 0.0  # top of clue area
    clue_cols: int = 3
    clue_gutter: float = 12.0
    clue_col_w: float = 0.0

    # Title text
    title: str = "CROSSWORD"


def render_pdf(
    grid: Grid,
    across: list[NumberedClue],
    down: list[NumberedClue],
    title: str,
    output_path: str,
) -> None:
    """Compute layout, adaptive fit, draw page 1 (puzzle) + page 2 (answer key)."""
    from reportlab.pdfgen.canvas import Canvas

    layout = _compute_layout(grid.size, across, down, title)
    layout = _adaptive_fit(across, down, layout)

    c = Canvas(output_path, pagesize=letter)

    # --- Page 1: Puzzle ---
    _draw_title_banner(c, layout)
    _draw_grid(c, grid, layout, show_answers=False)
    _draw_clue_zone(c, across, down, layout)
    c.showPage()

    # --- Page 2: Answer Key ---
    _draw_answer_key_page(c, grid, layout)
    c.showPage()

    c.save()


def _compute_layout(
    grid_size: int,
    across: list[NumberedClue],
    down: list[NumberedClue],
    title: str,
) -> LayoutParams:
    """Calculate all positions and sizes."""
    lp = LayoutParams(grid_size=grid_size, title=title)

    # Cell size scaling by grid size
    if grid_size <= 13:
        lp.cell_size = 24.0
        lp.number_font_size = 8.5
    elif grid_size <= 15:
        lp.cell_size = 24.0
        lp.number_font_size = 8.0
    elif grid_size <= 17:
        lp.cell_size = 21.0
        lp.number_font_size = 7.0
    else:
        lp.cell_size = 17.0
        lp.number_font_size = 6.0

    total_clues = len(across) + len(down)
    if total_clues < 40:
        lp.clue_cols = 3
    else:
        lp.clue_cols = 4

    _recompute_positions(lp)
    return lp


def _recompute_positions(lp: LayoutParams) -> None:
    """(Re)calculate derived positions from current params."""
    lp.grid_dim = lp.cell_size * lp.grid_size

    # Banner at very top of usable area
    lp.banner_y = lp.page_h - lp.margin - lp.banner_h

    # Grid: centered horizontally, starts below banner + small gap
    grid_top_y = lp.banner_y - 8
    lp.grid_x = (lp.page_w - lp.grid_dim) / 2
    lp.grid_y = grid_top_y

    # Clue zone: below the grid, full page width
    grid_bottom_y = grid_top_y - lp.grid_dim
    lp.clue_zone_y = grid_bottom_y - 12

    # Clue column widths
    total_gutter = lp.clue_gutter * (lp.clue_cols - 1)
    lp.clue_col_w = (lp.usable_w - total_gutter) / lp.clue_cols


def _adaptive_fit(
    across: list[NumberedClue],
    down: list[NumberedClue],
    layout: LayoutParams,
) -> LayoutParams:
    """Step through adjustments until all content fits on page 1."""
    for _ in range(12):
        if _content_fits(across, down, layout):
            return layout

        # Step 1: reduce font
        if layout.clue_font_size > 6.0:
            layout.clue_font_size -= 0.5
            layout.clue_leading = layout.clue_font_size + 1.5
            continue

        # Step 2: reduce space after
        if layout.space_after > 0.5:
            layout.space_after = 0.5
            continue

        # Step 3: add clue column
        if layout.clue_cols < 5:
            layout.clue_cols += 1
            _recompute_positions(layout)
            continue

        # Step 4: reduce cell size
        if layout.cell_size > 16:
            layout.cell_size -= 1
            _recompute_positions(layout)
            continue

        break

    return layout


def _content_fits(
    across: list[NumberedClue],
    down: list[NumberedClue],
    layout: LayoutParams,
) -> bool:
    """Check if all clues fit below the grid on page 1."""
    col_heights = _balanced_all_clues_heights(across, down, layout)
    max_col_h = max(col_heights) if col_heights else 0
    # Add section headers (~14pt each for ACROSS + DOWN labels within columns)
    max_col_h += 18

    available = layout.clue_zone_y - layout.margin
    return max_col_h <= available


def _balanced_all_clues_heights(
    across: list[NumberedClue],
    down: list[NumberedClue],
    layout: LayoutParams,
) -> list[float]:
    """Estimate column heights for across + down clues flowing into columns."""
    style = _clue_style(layout)
    col_heights = [0.0] * layout.clue_cols

    # Measure each clue
    all_items: list[tuple[str, NumberedClue]] = []
    for clue in across:
        all_items.append(("A", clue))
    for clue in down:
        all_items.append(("D", clue))

    # First pass: total height to estimate split
    section_header_h = 14.0
    across_h = section_header_h + 4
    for _, clue in all_items[:len(across)]:
        p = Paragraph(_clue_markup(clue), style)
        _, h = p.wrap(layout.clue_col_w, 10000)
        across_h += h + style.spaceAfter

    down_h = section_header_h + 4
    for _, clue in all_items[len(across):]:
        p = Paragraph(_clue_markup(clue), style)
        _, h = p.wrap(layout.clue_col_w, 10000)
        down_h += h + style.spaceAfter

    total_h = across_h + down_h
    target_per_col = total_h / layout.clue_cols

    # Simulate column distribution
    col_idx = 0
    current_h = 0.0
    # ACROSS header
    current_h += section_header_h + 4

    for i, (section, clue) in enumerate(all_items):
        # Insert DOWN header at section boundary
        if i == len(across):
            # Check if DOWN header should start a new column
            if current_h > target_per_col * 0.7:
                col_heights[col_idx] = current_h
                col_idx = min(col_idx + 1, layout.clue_cols - 1)
                current_h = 0.0
            current_h += section_header_h + 4

        p = Paragraph(_clue_markup(clue), style)
        _, h = p.wrap(layout.clue_col_w, 10000)
        clue_h = h + style.spaceAfter
        current_h += clue_h

        # Move to next column if we exceed target
        if current_h > target_per_col and col_idx < layout.clue_cols - 1:
            # Don't break right after a section header
            if current_h > section_header_h + 10:
                col_heights[col_idx] = current_h
                col_idx += 1
                current_h = 0.0

    col_heights[col_idx] = max(col_heights[col_idx], current_h)
    return col_heights


def _clue_style(layout: LayoutParams) -> ParagraphStyle:
    """Build a ParagraphStyle for clue text."""
    return ParagraphStyle(
        "ClueStyle",
        fontName="Helvetica",
        fontSize=layout.clue_font_size,
        leading=layout.clue_leading,
        spaceAfter=layout.space_after,
    )


def _clue_markup(clue: NumberedClue) -> str:
    """Format clue as ``<b>N.</b> text`` with XML escaping."""
    return f"<b>{clue.number}.</b> {escape(clue.clue_text)}"


# ─── Drawing functions ──────────────────────────────────────────────────────


def _draw_title_banner(c, layout: LayoutParams) -> None:
    """Black rect + white centered bold text."""
    x = layout.margin
    y = layout.banner_y
    w = layout.usable_w
    h = layout.banner_h

    c.setFillColorRGB(0, 0, 0)
    c.rect(x, y, w, h, fill=1, stroke=0)

    c.setFillColorRGB(1, 1, 1)
    c.setFont("Helvetica-Bold", 16)
    text_w = stringWidth(layout.title, "Helvetica-Bold", 16)
    tx = x + (w - text_w) / 2
    ty = y + (h - 16) / 2 + 2
    c.drawString(tx, ty, layout.title)


def _draw_grid(c, grid: Grid, layout: LayoutParams, show_answers: bool) -> None:
    """Draw the crossword grid: black/white cells, numbers, optional letters."""
    x0 = layout.grid_x
    y0 = layout.grid_y
    cs = layout.cell_size
    size = grid.size

    for r in range(size):
        for col in range(size):
            cell = grid.cells[r][col]
            cx = x0 + col * cs
            cy = y0 - (r + 1) * cs

            if cell.cell_type == CellType.BLACK:
                c.setFillColorRGB(0, 0, 0)
                c.rect(cx, cy, cs, cs, fill=1, stroke=0)
            else:
                c.setFillColorRGB(1, 1, 1)
                c.setStrokeColorRGB(0, 0, 0)
                c.setLineWidth(0.5)
                c.rect(cx, cy, cs, cs, fill=1, stroke=1)

                # Cell number (upper-left)
                if cell.number is not None:
                    c.setFillColorRGB(0, 0, 0)
                    c.setFont("Helvetica-Bold", layout.number_font_size)
                    c.drawString(
                        cx + 1.5,
                        cy + cs - layout.number_font_size - 1,
                        str(cell.number),
                    )

                # Answer letter (shifted down-right to avoid number)
                if show_answers and cell.letter:
                    c.setFillColorRGB(0, 0, 0)
                    font_size = cs * 0.45
                    c.setFont("Helvetica", font_size)
                    lw = stringWidth(cell.letter, "Helvetica", font_size)
                    lx = cx + cs * 0.55 - lw / 2
                    ly = cy + cs * 0.42 - font_size / 2
                    c.drawString(lx, ly, cell.letter)

    # Outer border
    c.setStrokeColorRGB(0, 0, 0)
    c.setLineWidth(1.5)
    c.rect(x0, y0 - size * cs, size * cs, size * cs, fill=0, stroke=1)


def _draw_clue_zone(
    c,
    across: list[NumberedClue],
    down: list[NumberedClue],
    layout: LayoutParams,
) -> None:
    """Draw all clues (across + down) in balanced multi-column layout below grid."""
    style = _clue_style(layout)
    section_header_h = 14.0

    # Measure all clue heights
    across_items: list[tuple[str, float]] = []
    for clue in across:
        p = Paragraph(_clue_markup(clue), style)
        _, h = p.wrap(layout.clue_col_w, 10000)
        across_items.append((_clue_markup(clue), h + style.spaceAfter))

    down_items: list[tuple[str, float]] = []
    for clue in down:
        p = Paragraph(_clue_markup(clue), style)
        _, h = p.wrap(layout.clue_col_w, 10000)
        down_items.append((_clue_markup(clue), h + style.spaceAfter))

    # Total height for across and down sections
    across_total = section_header_h + 4 + sum(h for _, h in across_items)
    down_total = section_header_h + 4 + sum(h for _, h in down_items)
    grand_total = across_total + down_total
    target_per_col = grand_total / layout.clue_cols

    # Build ordered list of render items: (type, markup_or_label, height)
    # type: 'header' or 'clue'
    render_items: list[tuple[str, str, float]] = []
    render_items.append(("header", "ACROSS", section_header_h))
    for markup, h in across_items:
        render_items.append(("clue", markup, h))
    render_items.append(("header", "DOWN", section_header_h))
    for markup, h in down_items:
        render_items.append(("clue", markup, h))

    # Distribute items into columns
    columns: list[list[tuple[str, str, float]]] = [[] for _ in range(layout.clue_cols)]
    col_heights = [0.0] * layout.clue_cols
    col_idx = 0

    for i, (item_type, content, h) in enumerate(render_items):
        item_h = h + (4 if item_type == "header" else 0)

        # Check if we should move to next column
        if (col_idx < layout.clue_cols - 1
                and col_heights[col_idx] > 0
                and col_heights[col_idx] + item_h > target_per_col * 1.05):
            # Don't leave a header stranded at bottom of column
            # If last item in this column is a header, move it to next col
            if (columns[col_idx]
                    and columns[col_idx][-1][0] == "header"):
                stray = columns[col_idx].pop()
                col_heights[col_idx] -= stray[2] + 4
                col_idx += 1
                columns[col_idx].append(stray)
                col_heights[col_idx] += stray[2] + 4
            else:
                col_idx += 1

        columns[col_idx].append((item_type, content, h))
        col_heights[col_idx] += item_h

    # Render columns
    for i, col_items in enumerate(columns):
        col_x = layout.margin + i * (layout.clue_col_w + layout.clue_gutter)
        current_y = layout.clue_zone_y

        for item_type, content, h in col_items:
            if item_type == "header":
                _draw_section_header(c, content, col_x, current_y, layout.clue_col_w)
                current_y -= section_header_h + 4
            else:
                p = Paragraph(content, style)
                p.wrap(layout.clue_col_w, 10000)
                p.drawOn(c, col_x, current_y - h)
                current_y -= h


def _draw_section_header(c, text: str, x: float, y: float, width: float) -> float:
    """Black rect + white bold text. Returns y at bottom of header."""
    h = 14
    c.setFillColorRGB(0, 0, 0)
    c.rect(x, y - h, width, h, fill=1, stroke=0)

    c.setFillColorRGB(1, 1, 1)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(x + 4, y - h + 3.5, text)

    return y - h


def _draw_answer_key_page(c, grid: Grid, layout: LayoutParams) -> None:
    """Draw the answer key page: banner + filled grid centered on page."""
    ak_layout = LayoutParams(
        grid_size=layout.grid_size,
        cell_size=layout.cell_size,
        number_font_size=layout.number_font_size,
        title="ANSWER KEY",
    )

    # Center the grid horizontally
    ak_layout.grid_dim = ak_layout.cell_size * ak_layout.grid_size
    ak_layout.banner_y = ak_layout.page_h - ak_layout.margin - ak_layout.banner_h
    ak_layout.grid_x = (ak_layout.page_w - ak_layout.grid_dim) / 2
    ak_layout.grid_y = ak_layout.banner_y - 20  # gap below banner

    _draw_title_banner(c, ak_layout)
    _draw_grid(c, grid, ak_layout, show_answers=True)
