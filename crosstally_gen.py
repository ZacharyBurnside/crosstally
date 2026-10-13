#!/usr/bin/env python3
"""
Crosstally generator.

A Crosstally puzzle is a small crossword where some answers have a normal clue and the rest have only a
number: the total of their letters (A=1 ... Z=26). The generator:

  1. fills a symmetric grid with common words, preferring words that have a clue in clue_bank.txt;
  2. chooses which answers become "number only";
  3. keeps the puzzle only if
       - with the clued words fixed, the totals leave exactly ONE fill of the number-only answers
         (checked against ~10,000 common words plus the whole clue bank), and
       - WITHOUT the totals, several fills remain (so the numbers are genuinely needed), and
       - most number-only answers have two or more unknown letters (so it takes vocabulary, not just
         subtraction).

Each puzzle is also given a level 1 (easiest) to 4 (hardest). For daily puzzles use make_daily.py, which
calls generate(..., need={1: 1, 2: 1, 3: 1, 4: 1}) and re-checks every result with validate.py.

Usage:
    pip install wordfreq english-words faker
    python crosstally_gen.py --size 5 --count 6 --seed 1 --out puzzles.json
    python crosstally_gen.py --size 5 --date 2026-10-14 --out today.json     # one deterministic daily puzzle

Output is a JSON list of {"grid": [...], "numOnly": [...], "clues": {...}, "meta": {..., "level": 1-4}}.
"""
import argparse, collections, datetime, itertools, json, os, random, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
BLACKLIST = set("fuck shit piss cock dick cunt rape porn sexy slut whore anus nazi penis".split())

# Proper nouns and abbreviations must never be answers. Unless a word is in the clue bank it is only used
# as a fill word when it is not on this list. (Faker's name lists are used too when the package is installed.)
MANUAL_NAMES = set("""
tim ken ivan devon blair alan alex amy ann anna anne bob dan dave eddie emma evan jack jake jane jim joe john jose juan
kate lars lee les lisa luke marie mary max nick paul rick roy ryan sam sean tom tony ted adam andy ben carl dean
dale gary greg hugh ian jay jeff jess joan joel jon josh karl kim kurt lana lena leo lois lou lucy mark matt mike
nina noah nora omar owen pam pete phil rita rob ron rosa russ ruth sara scot seth sue tara tina todd troy vera
iran iraq china india japan korea spain italy paris texas utah ohio iowa asia africa europe london berlin rome cuba
nepal egypt sri israel arab jews roma ibm nasa fbi cia usa ucla
del elf eds ing ugh tho thx hmm wow ooh duh yep yeah anti
""".split())


def name_block():
    block = set(MANUAL_NAMES)
    try:
        from faker.providers.person.en_US import Provider as P
        block |= {n.lower() for n in P.first_names} | {n.lower() for n in P.last_names}
    except Exception:
        pass
    return block


def val(word):
    return sum(ord(c) - 64 for c in word)


# ---------------------------------------------------------------- word lists
def load_words():
    from wordfreq import top_n_list, zipf_frequency
    from english_words import get_english_words_set
    dictionary = get_english_words_set(["web2"], lower=True, alpha=True)
    raw = [w for w in top_n_list("en", 60000)
           if 3 <= len(w) <= 6 and w.isalpha() and w.islower() and w in dictionary and w not in BLACKLIST]
    broad = collections.defaultdict(list)   # zipf >= 3.0: used to prove the totals leave one fill
    common = collections.defaultdict(list)  # zipf >= 3.8: used to prove the totals are needed
    for w in raw:
        z = zipf_frequency(w, "en")
        if z >= 3.0:
            broad[len(w)].append(w.upper())
        if z >= 3.8:
            common[len(w)].append(w.upper())
    return broad, common


AMBIG = set()   # words whose clue text is shared with another bank word; never shown as a clued answer


def load_bank(path=None):
    path = path or os.path.join(HERE, "clue_bank.txt")
    bank = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if "|" in line:
                w, c = line.split("|", 1)
                bank[w.strip().upper()] = c.strip()
    by_clue = collections.defaultdict(list)
    for w, c in bank.items():
        by_clue[c.lower()].append(w)
    AMBIG.clear()
    AMBIG.update(w for ws in by_clue.values() if len(ws) > 1 for w in ws)
    return bank


class Index:
    """Position/letter index so a slot pattern like 'D?E?' resolves to candidates quickly."""
    def __init__(self, words_by_len):
        self.words = {L: list(ws) for L, ws in words_by_len.items()}
        self.idx = {}
        for L, ws in self.words.items():
            m = collections.defaultdict(set)
            for i, w in enumerate(ws):
                for p, ch in enumerate(w):
                    m[(p, ch)].add(i)
            self.idx[L] = m

    def match(self, pattern, target_sum=None):
        L = len(pattern)
        sets = [self.idx[L][(p, ch)] for p, ch in enumerate(pattern) if ch != "?"]
        if sets:
            sets.sort(key=len)
            ids = set.intersection(*sets)
            out = [self.words[L][i] for i in ids]
        else:
            out = list(self.words[L])
        if target_sum is not None:
            out = [w for w in out if val(w) == target_sum]
        return out


# ---------------------------------------------------------------- grids
def slots_of(grid):
    n = len(grid)
    white = lambda r, c: 0 <= r < n and 0 <= c < n and grid[r][c] != "#"
    out = []
    for r in range(n):
        for c in range(n):
            if not white(r, c):
                continue
            if not white(r, c - 1) and white(r, c + 1):
                cells, k = [], c
                while white(r, k):
                    cells.append((r, k)); k += 1
                out.append(("A", cells))
            if not white(r - 1, c) and white(r + 1, c):
                cells, k = [], r
                while white(k, c):
                    cells.append((k, c)); k += 1
                out.append(("D", cells))
    return out


def pattern_ok(pat):
    n = len(pat)
    sl = slots_of(pat)
    if any(len(c) < 3 for _, c in sl):
        return False
    cover = collections.defaultdict(set)
    for d, cells in sl:
        for q in cells:
            cover[q].add(d)
    whites = [(r, c) for r in range(n) for c in range(n) if pat[r][c] == "."]
    if any(len(cover[q]) != 2 for q in whites):
        return False
    seen, stack = {whites[0]}, [whites[0]]
    while stack:
        r, c = stack.pop()
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            q = (r + dr, c + dc)
            if q in cover and q not in seen:
                seen.add(q); stack.append(q)
    return len(seen) == len(whites)


def random_pattern(n, k, rng):
    while True:
        g = [["."] * n for _ in range(n)]
        for _ in range(k):
            r, c = rng.randrange(n), rng.randrange(n)
            g[r][c] = "#"; g[n - 1 - r][n - 1 - c] = "#"
        pat = ["".join(row) for row in g]
        if pattern_ok(pat):
            return pat


def fill_grid(pat, rng, fill_index, bank, tlimit):
    n = len(pat)
    sl = slots_of(pat)
    grid = [[None if pat[r][c] == "." else "#" for c in range(n)] for r in range(n)]
    used, t0 = set(), time.time()

    def pattern(s):
        return "".join(grid[r][c] or "?" for r, c in s[1])

    def cands(s):
        ws = [w for w in fill_index.match(pattern(s)) if w not in used]
        rng.shuffle(ws)
        ws.sort(key=lambda w: w not in bank)   # bank words first, so most answers can be clued
        return ws

    def rec(todo):
        if time.time() - t0 > tlimit:
            return None
        if not todo:
            return True
        best, best_c = None, None
        for s in todo:
            c = cands(s)
            if not c:
                return False
            if best_c is None or len(c) < len(best_c):
                best, best_c = s, c
        rest = [s for s in todo if s is not best]
        for w in best_c[:30]:
            old = [grid[r][c] for r, c in best[1]]
            for ch, (r, c) in zip(w, best[1]):
                grid[r][c] = ch
            used.add(w)
            res = rec(rest)
            if res:
                return True
            used.discard(w)
            for ch, (r, c) in zip(old, best[1]):
                grid[r][c] = ch
            if res is None:
                return None
        return False

    return ["".join(row) for row in grid] if rec(sl) else None


# ---------------------------------------------------------------- number-only selection and checks
def count_fills(grid, numeric, known, index, use_sums, cap=50):
    """Count assignments of the number-only slots (clued letters fixed). Stops at `cap`."""
    order = sorted(numeric, key=lambda s: -sum(1 for q in s[1] if q in known))
    cells = {}
    total = 0

    def rec(i):
        nonlocal total
        if total >= cap:
            return
        if i == len(order):
            total += 1
            return
        s = order[i]
        pat = "".join(known.get(q) or cells.get(q) or "?" for q in s[1])
        target = val("".join(grid[r][c] for r, c in s[1])) if use_sums else None
        for w in index.match(pat, target):
            new = {q: ch for ch, q in zip(w, s[1]) if q not in known and q not in cells}
            cells.update(new)
            rec(i + 1)
            for q in new:
                del cells[q]

    rec(0)
    return total


def choose_numeric(grid, bank, rng, broad_index, common_index, tries=120, min_ambiguity=4):
    sl = slots_of(grid)
    word = lambda s: "".join(grid[r][c] for r, c in s[1])
    n_slots = len(sl)
    must = {i for i, s in enumerate(sl) if word(s) not in bank or word(s) in AMBIG}   # no usable clue -> number-only
    cover = collections.defaultdict(list)
    for i, s in enumerate(sl):
        for q in s[1]:
            cover[q].append(i)
    lo = max(len(must), 3)
    hi = max(lo, int(n_slots * 0.5))
    bests = {}
    for _ in range(tries):
        k = rng.randint(lo, hi)
        extra = rng.sample([i for i in range(n_slots) if i not in must], max(0, k - len(must)))
        U = set(must) | set(extra)
        unknown = {q for q, ids in cover.items() if all(i in U for i in ids)}
        numeric = [sl[i] for i in sorted(U)]
        if not (3 <= len(unknown) <= len(grid) + 3):
            continue
        per = [sum(1 for q in s[1] if q in unknown) for s in numeric]
        if min(per) < 1:
            continue                                           # every number-only answer needs a real unknown
        if sum(1 for p in per if p >= 2) * 2 < len(numeric):
            continue                                           # mostly arithmetic -> reject
        clued = [sl[i] for i in range(n_slots) if i not in U]
        clues = [bank[word(s)] for s in clued]
        if len(set(clues)) != len(clues):
            continue
        known = {q: grid[q[0]][q[1]] for q in cover if q not in unknown}
        with_sums = count_fills(grid, numeric, known, broad_index, True, cap=2)
        if with_sums != 1:
            continue
        without = count_fills(grid, numeric, known, common_index, False, cap=60)
        if without < min_ambiguity:
            continue
        score = (without, len(unknown))
        cand = {"numOnly": [word(s) for s in numeric],
                "clues": {word(s): bank[word(s)] for s in clued},
                "meta": {"unknown": len(unknown), "fillsWithoutTotals": without, "numberOnly": len(numeric),
                         "answers": n_slots}}
        lvl = level_of(cand["meta"])
        cand["meta"]["level"] = lvl
        cand["meta"]["difficulty"] = LABELS[lvl]
        if lvl not in bests or score > bests[lvl][0]:
            bests[lvl] = (score, cand)
    return {lvl: c for lvl, (_, c) in bests.items()}   # best candidate per difficulty level


LABELS = {1: "Easy", 2: "Medium", 3: "Hard", 4: "Expert"}


def level_of(meta):
    """Level 1 (easiest) to 4 (hardest): how many cells only the numbers can reveal, and how many
    answers have no clue. More unknown cells + more number-only words = more vocabulary guessing."""
    d = meta["unknown"] + meta["numberOnly"]
    return 1 if d <= 8 else 2 if d <= 9 else 3 if d <= 10 else 4


def generate(size, count, seed, tlimit=4.0, max_patterns=400, verbose=True, on_found=None, bank_only=True,
             need=None, avoid_words=None):
    rng = random.Random(seed)
    broad, common = load_words()
    bank = load_bank()
    for w in bank:                      # bank words count as valid alternatives when proving uniqueness
        if 3 <= len(w) <= 6 and w not in broad[len(w)]:
            broad[len(w)].append(w)
    broad_index, common_index = Index(broad), Index(common)
    avoid = set(avoid_words or [])
    fill_words = collections.defaultdict(list)
    seen, block = set(), {w.upper() for w in name_block()}
    for L in (3, 4, 5, 6):
        # Every answer comes from the clue bank (so it is a word a person knows and can be clued).
        # With bank_only=False, other common words that are not names/abbreviations are allowed as
        # number-only answers too; that widens the search but admits odder words (e.g. "midst").
        extra = [] if bank_only else [w for w in common[L] if w not in block]
        for w in [w for w in bank if len(w) == L and w not in avoid] + extra:
            if w not in seen:
                seen.add(w); fill_words[L].append(w)
    fill_index = Index(fill_words)
    out, seen_grids = [], set()
    for attempt in range(max_patterns):
        k = rng.choice([2, 3] if size == 5 else [3, 4])
        pat = random_pattern(size, k, rng)
        grid = fill_grid(pat, rng, fill_index, bank, tlimit)
        if not grid or tuple(grid) in seen_grids:
            continue
        seen_grids.add(tuple(grid))
        by_level = choose_numeric(grid, bank, rng, broad_index, common_index)
        if not by_level:
            continue
        if need is not None:
            options = [l for l in by_level if need.get(l, 0) > 0]
            if not options:
                continue
            lvl = max(options, key=lambda l: need[l])
            need[lvl] -= 1
        else:
            lvl = rng.choice(sorted(by_level))
        res = by_level[lvl]
        res["grid"] = grid
        out.append(res)
        if on_found:
            on_found(out)
        if verbose:
            print("found", len(out), "of", count, "level", lvl, res["meta"], file=sys.stderr)
        if len(out) >= count or (need is not None and not any(need.values())):
            break
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--size", type=int, default=5, choices=[5, 6])
    ap.add_argument("--count", type=int, default=6)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--date", help="YYYY-MM-DD: derive the seed from a date and make one puzzle")
    ap.add_argument("--time-limit", type=float, default=4.0, help="seconds per grid fill attempt")
    ap.add_argument("--out", default="puzzles.json")
    a = ap.parse_args()
    seed, count = a.seed, a.count
    if a.date:
        seed = int(datetime.date.fromisoformat(a.date).strftime("%Y%m%d"))
        count = 1
    def save(puzzles):
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(puzzles, f, indent=1)

    puzzles = generate(a.size, count, seed, a.time_limit, on_found=save)
    save(puzzles)
    print(f"wrote {len(puzzles)} puzzle(s) to {a.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
