"""Template-based crossword construction using blacksquare for grid filling.

Generates newspaper-quality 15×15 crosswords by:
1. Creating a symmetric grid template (black/white pattern)
2. Filling the template using blacksquare's DFS solver + 304K word dictionary
3. Looking up clues from our word bank
"""

from __future__ import annotations

import random
from collections import deque

from blacksquare import Crossword as BSCrossword
from blacksquare import BLACK as BS_BLACK

from models import CrosswordError, Direction, PlacedEntry
from word_bank import get_word_bank


def _has_clue(word: str, bank: dict[str, str], wn_known: set[str]) -> bool:
    """Check whether we can generate a real clue for this word.

    Returns True if the word is in our bank, derivable via inflection
    from a bank word, or present in WordNet.
    """
    if word in bank:
        return True
    # Inflection derivation (mirrors _auto_clue logic)
    if word.endswith("S") and len(word) >= 4:
        if word[:-1] in bank or word[:-2] in bank:
            return True
    if word.endswith("ED") and len(word) >= 5:
        if word[:-2] in bank or word[:-1] in bank:
            return True
    if word.endswith("ING") and len(word) >= 6:
        base = word[:-3]
        if base in bank or (base + "E") in bank:
            return True
    if word.endswith("ER") and len(word) >= 5:
        if word[:-2] in bank or word[:-1] in bank:
            return True
    if word.endswith("LY") and len(word) >= 5:
        if word[:-2] in bank:
            return True
    # WordNet
    return word in wn_known


def _build_wordnet_known(candidates: set[str]) -> set[str]:
    """Batch-check which candidate words exist in WordNet."""
    try:
        from nltk.corpus import wordnet as wn
    except ImportError:
        return set()
    return {w for w in candidates if wn.synsets(w.lower())}


def _build_merged_word_list() -> "BSWordList":
    """Build a merged word list: our bank (score 1.0) + clueable blacksquare words.

    Only includes words that we can actually generate clues for:
    either from our bank, via inflection derivation, or from WordNet.
    This guarantees zero 'Clue for X' fallbacks in the output.
    """
    from blacksquare.word_list import WordList as BSWordList

    bank = get_word_bank()
    default_wl = BSCrossword(num_rows=5, num_cols=5).word_list

    # Load system dictionary with common inflections
    dict_words: set[str] | None = None
    try:
        dict_words = set()
        with open("/usr/share/dict/words") as f:
            for line in f:
                w = line.strip().upper()
                dict_words.add(w)
                if len(w) >= 3:
                    for suffix in ("S", "ED", "ING", "ER", "LY", "ES", "D"):
                        dict_words.add(w + suffix)
    except FileNotFoundError:
        dict_words = None  # Fall back to unfiltered

    # Phase 1: collect dictionary-filtered candidates
    candidates: dict[str, float] = {}
    for word in default_wl.words:
        w_upper = word.upper()
        score = default_wl.get_score(word)
        if score >= 0.5:
            if dict_words is None or w_upper in dict_words:
                candidates[w_upper] = float(score) * 0.3

    # Phase 2: check which candidates need WordNet (not in bank, not inflectable)
    need_wn_check: set[str] = set()
    for w in candidates:
        if w not in bank and not _has_clue(w, bank, set()):
            need_wn_check.add(w)

    wn_known = _build_wordnet_known(need_wn_check)

    # Phase 3: filter — only keep words with a clue source
    merged: dict[str, float] = {}
    for w, score in candidates.items():
        if _has_clue(w, bank, wn_known):
            merged[w] = score
    for word in bank:
        merged[word] = 1.0

    return BSWordList(merged)


# Module-level cache for the merged word list
_merged_wl_cache: object | None = None


def _get_merged_word_list() -> "BSWordList":
    global _merged_wl_cache
    if _merged_wl_cache is None:
        _merged_wl_cache = _build_merged_word_list()
    return _merged_wl_cache


def generate_crossword(
    grid_size: int = 15,
    seed: int | None = None,
    retries: int = 30,
) -> list[PlacedEntry]:
    """Generate a newspaper-quality crossword from the word bank."""
    rng = random.Random(seed)
    bank = get_word_bank()
    word_list = _get_merged_word_list()

    best_result: list[PlacedEntry] | None = None

    for _ in range(retries):
        attempt_seed = rng.randint(0, 2**31)
        result = _single_template_attempt(
            grid_size, bank, random.Random(attempt_seed), word_list,
        )
        if result is not None:
            if best_result is None or len(result) > len(best_result):
                best_result = result
                if len(result) >= 60:
                    break

    if best_result is None or len(best_result) < 30:
        raise CrosswordError("Could not generate a valid crossword")

    return best_result


def _single_template_attempt(
    grid_size: int,
    bank: dict[str, str],
    rng: random.Random,
    word_list: object,
) -> list[PlacedEntry] | None:
    """Generate template, fill with blacksquare, look up clues."""
    template = _generate_template(grid_size, rng)
    if template is None:
        return None

    xw = BSCrossword(num_rows=grid_size, num_cols=grid_size)
    for r in range(grid_size):
        for c in range(grid_size):
            if template[r][c]:
                xw[r, c] = BS_BLACK

    try:
        filled = xw.fill(timeout=30, temperature=0.5, word_list=word_list)
    except Exception:
        return None

    if filled is None:
        return None

    placed = []
    for word_obj in filled.iterwords():
        answer = str(word_obj.value).strip().upper()
        if not answer:
            continue

        cell0 = word_obj.cells[0]
        row, col = cell0.index

        bs_dir = word_obj.direction
        direction = (Direction.ACROSS
                     if bs_dir.name == "ACROSS"
                     else Direction.DOWN)

        clue = bank.get(answer) or _auto_clue(answer, bank)

        placed.append(PlacedEntry(
            number=0,
            clue_text=clue,
            answer=answer,
            row=int(row),
            col=int(col),
            direction=direction,
        ))

    return placed


# ── Auto-clue generation via WordNet ────────────────────────────────

def _wordnet_clue(word: str) -> str | None:
    """Look up a short crossword-style clue from WordNet."""
    try:
        from nltk.corpus import wordnet as wn
    except ImportError:
        return None

    w_lower = word.lower()
    synsets = wn.synsets(w_lower)
    if not synsets:
        return None

    def _clean(defn: str) -> str:
        """Strip parentheticals and trailing clauses."""
        paren = defn.find(" (")
        if paren > 5:
            defn = defn[:paren]
        semi = defn.find("; ")
        if semi > 5:
            defn = defn[:semi]
        return defn.strip()

    max_len = 35  # Must fit PDF across-clue column without wrapping

    def _truncate(defn: str) -> str:
        """Truncate at word boundary."""
        if len(defn) <= max_len:
            return defn
        cut = defn[:max_len].rfind(" ")
        return defn[:cut] if cut > 5 else defn[:max_len]

    # Pass 1: synsets where our word is the PRIMARY lemma (correct sense)
    # Pass 2: all remaining synsets
    primary = []
    secondary = []
    for syn in synsets:
        defn = _clean(syn.definition())
        if w_lower in defn.lower().split():
            continue
        is_primary = syn.lemmas()[0].name().lower() == w_lower
        (primary if is_primary else secondary).append(defn)

    # Primary senses: prefer shortest (most crossword-like)
    # Secondary senses: keep WordNet order (most common first)
    primary.sort(key=len)

    for defn in primary + secondary:
        if len(defn) <= max_len:
            return defn[0].upper() + defn[1:]

    # All too long — truncate the best one
    for defn in primary + secondary:
        defn = _truncate(defn)
        return defn[0].upper() + defn[1:]

    # Last resort: first synset, truncated
    defn = _truncate(_clean(synsets[0].definition()))
    return defn[0].upper() + defn[1:]


# Cache WordNet lookups across calls within a single run
_wordnet_cache: dict[str, str | None] = {}


def _auto_clue(answer: str, bank: dict[str, str]) -> str:
    """Generate a clue for a word not in the bank.

    Priority:
    1. Derive from bank base form (plural, past tense, etc.)
    2. Look up definition in WordNet
    3. Fall back to "Clue for WORD"
    """
    # Try to derive clue from base form in the bank
    # Plural -S / -ES
    if answer.endswith("S") and len(answer) >= 4:
        base = answer[:-1]
        if base in bank:
            return bank[base] + ", pl."
        base_es = answer[:-2]
        if base_es in bank:
            return bank[base_es] + ", pl."
    # Past tense -ED
    if answer.endswith("ED") and len(answer) >= 5:
        base = answer[:-2]
        if base in bank:
            return bank[base] + ", past tense"
        base_d = answer[:-1]
        if base_d in bank:
            return bank[base_d] + ", past tense"
    # -ING
    if answer.endswith("ING") and len(answer) >= 6:
        base = answer[:-3]
        if base in bank:
            return bank[base] + ", ongoing"
        base_e = base + "E"
        if base_e in bank:
            return bank[base_e] + ", ongoing"
    # -ER comparative / agent
    if answer.endswith("ER") and len(answer) >= 5:
        base = answer[:-2]
        if base in bank:
            return "More " + bank[base].lower()
        base_e = answer[:-1]
        if base_e in bank:
            return bank[base_e] + " person"
    # -LY adverb
    if answer.endswith("LY") and len(answer) >= 5:
        base = answer[:-2]
        if base in bank:
            return "In a " + bank[base].lower() + " way"

    # WordNet lookup
    if answer not in _wordnet_cache:
        _wordnet_cache[answer] = _wordnet_clue(answer)
    wn_clue = _wordnet_cache[answer]
    if wn_clue:
        return wn_clue

    return f"Clue for {answer}"


# ── Template generation ──────────────────────────────────────────────

def _generate_template(
    grid_size: int,
    rng: random.Random,
    target_black: int | None = None,
    max_word_len: int = 8,
) -> list[list[bool]] | None:
    """Generate a symmetric grid template with balanced slot lengths.

    Returns 2D bool array where True = black cell.
    Uses retry loop with independent random attempts.
    """
    if target_black is None:
        target_black = int(grid_size * grid_size * 0.22)  # ~50 for 15×15

    for _ in range(50):
        result = _try_template(grid_size, rng, target_black, max_word_len)
        if result is not None:
            return result
    return None


def _try_template(
    grid_size: int,
    rng: random.Random,
    target_black: int,
    max_word_len: int,
) -> list[list[bool]] | None:
    """Single attempt at generating a valid symmetric template."""
    black = [[False] * grid_size for _ in range(grid_size)]
    placed_count = 0

    # Phase 1: Break all runs longer than max_word_len
    # During this phase, only check that no 1-2 cell runs are created.
    # We can't check max_word_len yet because unbroken runs still exist.
    for _ in range(200):
        candidates = _find_long_run_breaks(black, grid_size, max_word_len)
        if not candidates:
            break  # All runs are within limit

        rng.shuffle(candidates)

        placed = False
        for br, bc in candidates[:30]:
            if black[br][bc]:
                continue
            sr, sc = grid_size - 1 - br, grid_size - 1 - bc
            if (sr, sc) != (br, bc) and black[sr][sc]:
                continue

            black[br][bc] = True
            if (sr, sc) != (br, bc):
                black[sr][sc] = True

            if _no_short_runs_affected(black, grid_size, br, bc, sr, sc):
                placed_count += (2 if (sr, sc) != (br, bc) else 1)
                placed = True
                break

            black[br][bc] = False
            if (sr, sc) != (br, bc):
                black[sr][sc] = False

        if not placed:
            return None  # Stuck, can't break remaining long runs

    # Verify all runs are now <= max_word_len
    if _has_long_runs(black, grid_size, max_word_len):
        return None

    # Phase 2: Add random black cells to reach target count
    cells = [(r, c) for r in range(grid_size) for c in range(grid_size)]
    rng.shuffle(cells)

    for r, c in cells:
        if placed_count >= target_black:
            break
        if black[r][c]:
            continue

        sr, sc = grid_size - 1 - r, grid_size - 1 - c
        if (sr, sc) != (r, c) and black[sr][sc]:
            continue

        black[r][c] = True
        if (sr, sc) != (r, c):
            black[sr][sc] = True

        # Only check no short runs — adding black cells can't create longer runs
        if _no_short_runs_affected(black, grid_size, r, c, sr, sc):
            placed_count += (2 if (sr, sc) != (r, c) else 1)
        else:
            black[r][c] = False
            if (sr, sc) != (r, c):
                black[sr][sc] = False

    # Final full validation (run lengths, connectivity)
    if not _is_valid_template(black, grid_size, max_word_len):
        return None

    return black


def _find_long_run_breaks(
    black: list[list[bool]],
    grid_size: int,
    max_word_len: int,
) -> list[tuple[int, int]]:
    """Find candidate positions to break runs exceeding max_word_len."""
    candidates = []

    for r in range(grid_size):
        c = 0
        while c < grid_size:
            if black[r][c]:
                c += 1
                continue
            start = c
            while c < grid_size and not black[r][c]:
                c += 1
            if c - start > max_word_len:
                for pos in range(start + 3, c - 3):
                    candidates.append((r, pos))

    for c in range(grid_size):
        r = 0
        while r < grid_size:
            if black[r][c]:
                r += 1
                continue
            start = r
            while r < grid_size and not black[r][c]:
                r += 1
            if r - start > max_word_len:
                for pos in range(start + 3, r - 3):
                    candidates.append((pos, c))

    return candidates


def _has_long_runs(
    black: list[list[bool]], grid_size: int, max_word_len: int,
) -> bool:
    """Check if any white run exceeds max_word_len."""
    for r in range(grid_size):
        c = 0
        while c < grid_size:
            if black[r][c]:
                c += 1
                continue
            start = c
            while c < grid_size and not black[r][c]:
                c += 1
            if c - start > max_word_len:
                return True

    for c in range(grid_size):
        r = 0
        while r < grid_size:
            if black[r][c]:
                r += 1
                continue
            start = r
            while r < grid_size and not black[r][c]:
                r += 1
            if r - start > max_word_len:
                return True

    return False


def _no_short_runs_affected(
    black: list[list[bool]],
    grid_size: int,
    r1: int, c1: int,
    r2: int, c2: int,
) -> bool:
    """Check that no 1-2 cell white runs exist in rows/columns affected by placement."""
    for r in {r1, r2}:
        c = 0
        while c < grid_size:
            if black[r][c]:
                c += 1
                continue
            start = c
            while c < grid_size and not black[r][c]:
                c += 1
            if 1 <= (c - start) <= 2:
                return False

    for c in {c1, c2}:
        r = 0
        while r < grid_size:
            if black[r][c]:
                r += 1
                continue
            start = r
            while r < grid_size and not black[r][c]:
                r += 1
            if 1 <= (r - start) <= 2:
                return False

    return True


def _is_valid_template(
    black: list[list[bool]], grid_size: int, max_word_len: int = 15,
) -> bool:
    """Full template validation: min word length 3, max word length, all white connected."""
    for r in range(grid_size):
        c = 0
        while c < grid_size:
            if black[r][c]:
                c += 1
                continue
            start = c
            while c < grid_size and not black[r][c]:
                c += 1
            run_len = c - start
            if 1 <= run_len <= 2:
                return False
            if run_len > max_word_len:
                return False

    for c in range(grid_size):
        r = 0
        while r < grid_size:
            if black[r][c]:
                r += 1
                continue
            start = r
            while r < grid_size and not black[r][c]:
                r += 1
            run_len = r - start
            if 1 <= run_len <= 2:
                return False
            if run_len > max_word_len:
                return False

    # Check connectivity (all white cells connected)
    start_r = start_c = -1
    white_count = 0
    for r in range(grid_size):
        for c in range(grid_size):
            if not black[r][c]:
                white_count += 1
                if start_r == -1:
                    start_r, start_c = r, c

    if white_count == 0:
        return False

    # BFS from first white cell
    visited = set()
    queue = deque([(start_r, start_c)])
    visited.add((start_r, start_c))
    while queue:
        r, c = queue.popleft()
        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nr, nc = r + dr, c + dc
            if 0 <= nr < grid_size and 0 <= nc < grid_size:
                if not black[nr][nc] and (nr, nc) not in visited:
                    visited.add((nr, nc))
                    queue.append((nr, nc))

    return len(visited) == white_count
