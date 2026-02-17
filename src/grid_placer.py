"""Crossword word placement: greedy fill (short-word preference) + simulated annealing."""

from __future__ import annotations

import math
import random
from collections import namedtuple
from typing import Optional

from models import ClueEntry, CrosswordError, Direction, PlacedEntry

Candidate = namedtuple("Candidate", ["row", "col", "direction", "intersections"])
WorkingGrid = list[list[Optional[str]]]


def compute_grid_size(clues: list[ClueEntry], target_words: int = 65) -> int:
    """Compute optimal grid size based on word list statistics.

    Uses empirical formula: words_placed ≈ 0.175 * grid_size^2.
    """
    if not clues:
        return 15
    # Empirical: algorithm places ~0.175 * grid_size^2 words with SA refinement
    raw = math.sqrt(target_words / 0.175)
    # Round to nearest odd number, minimum 15
    size = max(15, round(raw))
    if size % 2 == 0:
        size += 1
    return size


def place_words(
    clues: list[ClueEntry],
    grid_size: int = 15,
    seed: int | None = None,
    retries: int = 20,
    symmetry: bool = False,
) -> list[PlacedEntry]:
    """Run *retries* placement attempts, return the best result.

    Raises CrosswordError if the best attempt places fewer than 30 words.
    """
    if symmetry:
        retries = max(retries, 40)

    best_placed: list[PlacedEntry] | None = None
    best_stats: dict | None = None

    rng = random.Random(seed)

    for _ in range(retries):
        attempt_seed = rng.randint(0, 2**31)
        placed, stats = _single_attempt(clues, grid_size, random.Random(attempt_seed), symmetry)
        if best_placed is None or _compare_attempts(stats, best_stats) > 0:
            best_placed, best_stats = placed, stats

    if len(best_placed) < 30:
        raise CrosswordError(
            f"Best attempt placed only {len(best_placed)} words (minimum 30 required)"
        )

    return best_placed


# ── Pre-computation ──────────────────────────────────────────────────

def _build_letter_index(
    clues: list[ClueEntry],
) -> dict[str, list[tuple[ClueEntry, int]]]:
    """Map letter -> [(clue, position_in_word)] for fast crossing lookups."""
    idx: dict[str, list[tuple[ClueEntry, int]]] = {}
    for clue in clues:
        for i, ch in enumerate(clue.answer):
            idx.setdefault(ch, []).append((clue, i))
    return idx


# ── Core placement algorithm ─────────────────────────────────────────

def _single_attempt(
    clues: list[ClueEntry],
    grid_size: int,
    rng: random.Random,
    symmetry: bool,
) -> tuple[list[PlacedEntry], dict]:
    """Greedy fill with roulette selection, then simulated annealing refinement."""
    working: WorkingGrid = [[None] * grid_size for _ in range(grid_size)]
    reserved: set[tuple[int, int]] = set()
    placed: list[PlacedEntry] = []
    placed_answers: set[str] = set()

    letter_index = _build_letter_index(clues)

    # Prefer short words: sort by length, short first
    sorted_clues = sorted(clues, key=lambda c: len(c.answer))

    # ── Stage 1: Greedy forward pass ──
    # Seed: pick a medium-length word for good crossing potential
    mid_words = [c for c in clues if 5 <= len(c.answer) <= 7]
    if not mid_words:
        mid_words = sorted_clues[len(sorted_clues) // 2:]
    seed_word = rng.choice(mid_words)
    center = grid_size // 2
    first_col = max(0, (grid_size - len(seed_word.answer)) // 2)
    _place_word(seed_word, center, first_col, Direction.ACROSS,
                working, placed, placed_answers, symmetry, grid_size, reserved)

    _greedy_fill(sorted_clues, working, grid_size, placed, placed_answers,
                 letter_index, symmetry, reserved, rng, max_stale=3, top_k=5)

    # ── Stage 2: Simulated Annealing ──
    best_placed = [p for p in placed]
    best_working = [row[:] for row in working]
    best_answers = set(placed_answers)
    best_count = len(placed)

    sa_iterations = 200
    temp_start = 6.0
    temp_end = 0.05

    for iteration in range(sa_iterations):
        temp = temp_start * (temp_end / temp_start) ** (iteration / max(sa_iterations - 1, 1))

        removable = [p for p in placed if p is not placed[0]]
        if len(removable) < 3:
            break

        # Alternate between cluster removal and random removal
        if iteration % 3 == 0:
            to_remove = _cluster_remove(removable, rng, grid_size)
        else:
            k = min(rng.randint(3, 7), len(removable))
            weights = [len(p.answer) ** 2.0 for p in removable]
            to_remove = _weighted_sample(removable, weights, k, rng)

        saved_working = [row[:] for row in working]
        saved_placed = list(placed)
        saved_answers = set(placed_answers)

        for p in to_remove:
            _remove_word(p, placed, working)
            placed.remove(p)
            placed_answers.discard(p.answer)

        _greedy_fill(sorted_clues, working, grid_size, placed, placed_answers,
                     letter_index, symmetry, reserved, rng, max_stale=2, top_k=3)

        delta = len(placed) - len(saved_placed)
        accept = (delta > 0 or
                  (delta >= -1 and rng.random() < math.exp(delta / max(temp, 0.01))))

        if accept:
            if len(placed) > best_count:
                best_placed = [p for p in placed]
                best_working = [row[:] for row in working]
                best_answers = set(placed_answers)
                best_count = len(placed)
        else:
            working[:] = saved_working
            placed[:] = saved_placed
            placed_answers.clear()
            placed_answers.update(saved_answers)

    # Restore best
    working[:] = best_working
    placed[:] = best_placed
    placed_answers.clear()
    placed_answers.update(best_answers)

    total_intersections = sum(_count_intersections_snapshot(p, placed) for p in placed)
    stats = {
        "word_count": len(placed),
        "intersections": total_intersections,
        "compactness": _compactness(working, grid_size),
    }
    return placed, stats


def _cluster_remove(
    removable: list[PlacedEntry], rng: random.Random, grid_size: int,
) -> list[PlacedEntry]:
    """Remove a spatial cluster of words near a random pivot point."""
    pivot = rng.choice(removable)
    pr = pivot.row + (len(pivot.answer) // 2 if pivot.direction == Direction.DOWN else 0)
    pc = pivot.col + (len(pivot.answer) // 2 if pivot.direction == Direction.ACROSS else 0)
    radius = rng.randint(3, 5)

    nearby = []
    for p in removable:
        mr = p.row + (len(p.answer) // 2 if p.direction == Direction.DOWN else 0)
        mc = p.col + (len(p.answer) // 2 if p.direction == Direction.ACROSS else 0)
        if abs(mr - pr) + abs(mc - pc) <= radius:
            nearby.append(p)

    # Remove 3-8 from the cluster
    k = min(rng.randint(3, 8), len(nearby))
    return nearby[:k]


def _greedy_fill(
    sorted_clues: list[ClueEntry], working: WorkingGrid, grid_size: int,
    placed: list[PlacedEntry], placed_answers: set[str],
    letter_index: dict, symmetry: bool, reserved: set,
    rng: random.Random, max_stale: int = 3, top_k: int = 1,
) -> None:
    """Greedy fill loop with roulette selection from top-K candidates."""
    stale = 0
    while stale < max_stale:
        remaining = [c for c in sorted_clues if c.answer not in placed_answers]
        if not remaining:
            break

        # Collect all (clue, candidate, score) triples
        scored: list[tuple[ClueEntry, Candidate, float]] = []
        for clue in remaining:
            candidates = _find_candidates(clue.answer, working, grid_size, symmetry, reserved)
            for cand in candidates:
                s = _score_candidate(cand, clue, working, grid_size, placed_answers,
                                     sorted_clues, letter_index, rng)
                scored.append((clue, cand, s))

        if not scored:
            stale += 1
            continue

        stale = 0

        # Pick from top-K using roulette selection
        scored.sort(key=lambda x: x[2], reverse=True)
        top = scored[:max(top_k, 1)]
        if len(top) == 1:
            pick = top[0]
        else:
            min_s = top[-1][2]
            weights = [x[2] - min_s + 0.1 for x in top]
            total_w = sum(weights)
            r = rng.uniform(0, total_w)
            cumul = 0.0
            pick = top[0]
            for i, (cl, ca, sc) in enumerate(top):
                cumul += weights[i]
                if cumul >= r:
                    pick = (cl, ca, sc)
                    break

        _place_word(pick[0], pick[1].row, pick[1].col, pick[1].direction,
                    working, placed, placed_answers, symmetry, grid_size, reserved)


def _place_word(
    clue: ClueEntry, row: int, col: int, direction: Direction,
    working: WorkingGrid, placed: list[PlacedEntry], placed_answers: set[str],
    symmetry: bool, grid_size: int, reserved: set[tuple[int, int]],
) -> None:
    _place_on_grid(clue.answer, row, col, direction, working)
    if symmetry:
        _mark_symmetric_reserved(row, col, len(clue.answer), direction, grid_size, reserved)
    placed.append(PlacedEntry(
        number=clue.number, clue_text=clue.clue_text, answer=clue.answer,
        row=row, col=col, direction=direction,
    ))
    placed_answers.add(clue.answer)


def _weighted_sample(
    items: list, weights: list[float], k: int, rng: random.Random,
) -> list:
    """Sample k items without replacement, weighted by weights."""
    selected = []
    pool = list(zip(items, weights))
    for _ in range(min(k, len(pool))):
        total = sum(w for _, w in pool)
        if total <= 0:
            break
        r = rng.uniform(0, total)
        cumulative = 0.0
        for idx, (item, w) in enumerate(pool):
            cumulative += w
            if cumulative >= r:
                selected.append(item)
                pool.pop(idx)
                break
    return selected


# ── Candidate finding ─────────────────────────────────────────────────

def _find_candidates(
    answer: str, working: WorkingGrid, grid_size: int,
    symmetry: bool, reserved: set[tuple[int, int]],
) -> list[Candidate]:
    """Find valid positions that intersect existing words."""
    candidates: list[Candidate] = []
    length = len(answer)
    answer_chars = set(answer)

    for direction in (Direction.ACROSS, Direction.DOWN):
        dr = 1 if direction == Direction.DOWN else 0
        dc = 1 if direction == Direction.ACROSS else 0
        checked: set[tuple[int, int]] = set()

        for r in range(grid_size):
            for c in range(grid_size):
                existing = working[r][c]
                if existing is None or existing not in answer_chars:
                    continue
                for i, ch in enumerate(answer):
                    if ch != existing:
                        continue
                    sr = r - dr * i
                    sc = c - dc * i
                    if sr < 0 or sc < 0:
                        continue
                    if sr + dr * (length - 1) >= grid_size:
                        continue
                    if sc + dc * (length - 1) >= grid_size:
                        continue
                    key = (sr, sc, dr)
                    if key in checked:
                        continue
                    checked.add(key)
                    if not _is_valid_placement(answer, sr, sc, direction, working, grid_size, symmetry, reserved):
                        continue
                    inters = _count_intersections(answer, sr, sc, direction, working)
                    if inters > 0:
                        candidates.append(Candidate(sr, sc, direction, inters))
    return candidates


# ── Scoring ───────────────────────────────────────────────────────────

def _score_candidate(
    candidate: Candidate, clue: ClueEntry, working: WorkingGrid,
    grid_size: int, placed_answers: set[str], all_clues: list[ClueEntry],
    letter_index: dict[str, list[tuple[ClueEntry, int]]], rng: random.Random,
) -> float:
    """Score a placement candidate. Prefers:
    - More intersections with existing words
    - Shorter words (they leave more room for future placements)
    - Central positions
    - Positions with future crossing potential
    """
    r, c, direction, intersections = candidate
    length = len(clue.answer)
    dr = 1 if direction == Direction.DOWN else 0
    dc = 1 if direction == Direction.ACROSS else 0

    # 1. Intersection density (intersections per letter)
    score = 4.0 * intersections

    # 2. Short word bonus: shorter words are more valuable for dense packing
    score += max(0, 8 - length) * 0.8

    # 3. Centrality bonus
    center = (grid_size - 1) / 2.0
    mid_r = r + dr * (length - 1) / 2.0
    mid_c = c + dc * (length - 1) / 2.0
    dist = (abs(mid_r - center) + abs(mid_c - center)) / grid_size
    score -= dist * 1.0

    # 4. Future crossing potential (lightweight check)
    cross_dir = Direction.DOWN if direction == Direction.ACROSS else Direction.ACROSS
    cross_dr = 1 if cross_dir == Direction.DOWN else 0
    cross_dc = 1 if cross_dir == Direction.ACROSS else 0

    future = 0
    for i in range(length):
        cr = r + dr * i
        cc = c + dc * i
        if working[cr][cc] is not None:
            continue
        letter = clue.answer[i]
        for other_clue, j in letter_index.get(letter, []):
            if other_clue.answer in placed_answers or other_clue.answer == clue.answer:
                continue
            osr = cr - cross_dr * j
            osc = cc - cross_dc * j
            if osr < 0 or osc < 0:
                continue
            olen = len(other_clue.answer)
            if osr + cross_dr * (olen - 1) >= grid_size:
                continue
            if osc + cross_dc * (olen - 1) >= grid_size:
                continue
            future += 1
            break

    score += future * 0.6

    # 5. Small jitter
    score += rng.uniform(0, 0.4)

    return score


# ── Validation ────────────────────────────────────────────────────────

def _is_valid_placement(
    answer: str, row: int, col: int, direction: Direction,
    working: WorkingGrid, grid_size: int, symmetry: bool,
    reserved: set[tuple[int, int]],
) -> bool:
    """Check letter matching, no extension, no 2-letter perpendicular stubs."""
    length = len(answer)
    dr = 1 if direction == Direction.DOWN else 0
    dc = 1 if direction == Direction.ACROSS else 0

    # Cell before start must be empty/edge
    br, bc = row - dr, col - dc
    if 0 <= br < grid_size and 0 <= bc < grid_size and working[br][bc] is not None:
        return False

    # Cell after end must be empty/edge
    ar, ac = row + dr * length, col + dc * length
    if 0 <= ar < grid_size and 0 <= ac < grid_size and working[ar][ac] is not None:
        return False

    # Perpendicular offsets
    pr = 1 if direction == Direction.ACROSS else 0
    pc = 1 if direction == Direction.DOWN else 0

    for i, letter in enumerate(answer):
        r = row + dr * i
        c = col + dc * i

        if symmetry and (r, c) in reserved:
            return False

        existing = working[r][c]

        if existing is not None:
            if existing != letter:
                return False
        else:
            # Check perpendicular neighbors won't create 2-letter stubs
            has_pp = (0 <= r + pr < grid_size and 0 <= c + pc < grid_size
                      and working[r + pr][c + pc] is not None)
            has_pm = (0 <= r - pr < grid_size and 0 <= c - pc < grid_size
                      and working[r - pr][c - pc] is not None)

            if has_pp or has_pm:
                run = 1
                nr, nc = r + pr, c + pc
                while 0 <= nr < grid_size and 0 <= nc < grid_size and working[nr][nc] is not None:
                    run += 1
                    nr += pr
                    nc += pc
                nr, nc = r - pr, c - pc
                while 0 <= nr < grid_size and 0 <= nc < grid_size and working[nr][nc] is not None:
                    run += 1
                    nr -= pr
                    nc -= pc
                if run == 2:
                    return False

    return True


# ── Grid manipulation ─────────────────────────────────────────────────

def _count_intersections(
    answer: str, row: int, col: int, direction: Direction, working: WorkingGrid
) -> int:
    dr = 1 if direction == Direction.DOWN else 0
    dc = 1 if direction == Direction.ACROSS else 0
    return sum(1 for i in range(len(answer)) if working[row + dr * i][col + dc * i] is not None)


def _count_intersections_snapshot(entry: PlacedEntry, all_placed: list[PlacedEntry]) -> int:
    """Count how many OTHER placed words cross this entry."""
    my_cells = set()
    dr = 1 if entry.direction == Direction.DOWN else 0
    dc = 1 if entry.direction == Direction.ACROSS else 0
    for i in range(len(entry.answer)):
        my_cells.add((entry.row + dr * i, entry.col + dc * i))

    count = 0
    for other in all_placed:
        if other is entry:
            continue
        odr = 1 if other.direction == Direction.DOWN else 0
        odc = 1 if other.direction == Direction.ACROSS else 0
        for i in range(len(other.answer)):
            if (other.row + odr * i, other.col + odc * i) in my_cells:
                count += 1
    return count


def _word_interconnections(
    entry: PlacedEntry, all_placed: list[PlacedEntry],
    working: WorkingGrid, grid_size: int,
) -> int:
    return _count_intersections_snapshot(entry, all_placed)


def _place_on_grid(
    answer: str, row: int, col: int, direction: Direction, working: WorkingGrid,
) -> None:
    dr = 1 if direction == Direction.DOWN else 0
    dc = 1 if direction == Direction.ACROSS else 0
    for i, letter in enumerate(answer):
        working[row + dr * i][col + dc * i] = letter


def _remove_word(
    entry: PlacedEntry, all_placed: list[PlacedEntry], working: WorkingGrid,
) -> None:
    """Remove a word from the grid, preserving cells shared with other placed words."""
    dr = 1 if entry.direction == Direction.DOWN else 0
    dc = 1 if entry.direction == Direction.ACROSS else 0

    shared_cells: set[tuple[int, int]] = set()
    for other in all_placed:
        if other is entry:
            continue
        odr = 1 if other.direction == Direction.DOWN else 0
        odc = 1 if other.direction == Direction.ACROSS else 0
        for i in range(len(other.answer)):
            shared_cells.add((other.row + odr * i, other.col + odc * i))

    for i in range(len(entry.answer)):
        r = entry.row + dr * i
        c = entry.col + dc * i
        if (r, c) not in shared_cells:
            working[r][c] = None


def _mark_symmetric_reserved(
    row: int, col: int, length: int, direction: Direction,
    grid_size: int, reserved: set[tuple[int, int]],
) -> None:
    dr = 1 if direction == Direction.DOWN else 0
    dc = 1 if direction == Direction.ACROSS else 0
    for i in range(length):
        r, c = row + dr * i, col + dc * i
        reserved.add((grid_size - 1 - r, grid_size - 1 - c))


# ── Metrics ───────────────────────────────────────────────────────────

def _compactness(working: WorkingGrid, grid_size: int) -> float:
    min_r = min_c = grid_size
    max_r = max_c = -1
    white = 0
    for r in range(grid_size):
        for c in range(grid_size):
            if working[r][c] is not None:
                white += 1
                min_r, max_r = min(min_r, r), max(max_r, r)
                min_c, max_c = min(min_c, c), max(max_c, c)
    if max_r == -1:
        return 0.0
    return white / ((max_r - min_r + 1) * (max_c - min_c + 1))


def _compare_attempts(a: dict, b: dict) -> int:
    if a["word_count"] != b["word_count"]:
        return a["word_count"] - b["word_count"]
    if a["intersections"] != b["intersections"]:
        return a["intersections"] - b["intersections"]
    if a["compactness"] > b["compactness"]:
        return 1
    elif a["compactness"] < b["compactness"]:
        return -1
    return 0
