"""Independent puzzle validator (does not share code with the generator's search).

    python3 validate.py daily/*.json          # check shipped files
    from validate import validate_puzzle      # used by make_daily.py before anything is written

A puzzle passes when:
  * every across/down slot is either clued or number-only (and not both);
  * clue texts are unique inside the puzzle and no clued answer shares its clue with another bank word;
  * with the totals, exactly ONE fill exists (checked against ~10k words: wordfreq zipf>=3.0 + the clue bank);
  * without the totals, at least 4 fills exist (so the numbers are really needed).
"""
import json, os, sys, functools

HERE = os.path.dirname(os.path.abspath(__file__))


def val(w):
    return sum(ord(c) - 64 for c in w)


@functools.lru_cache(maxsize=1)
def vocab():
    from wordfreq import top_n_list, zipf_frequency
    bank = {}
    for l in open(os.path.join(HERE, "clue_bank.txt"), encoding="utf8"):
        if "|" in l:
            w, c = l.rstrip("\n").split("|", 1)
            bank[w.upper()] = c.strip().lower()
    words = {w.upper() for w in top_n_list("en", 60000)
             if w.isalpha() and 3 <= len(w) <= 6 and zipf_frequency(w, "en") >= 3.0} | set(bank)
    by_clue = {}
    for w, c in bank.items():
        by_clue.setdefault(c, []).append(w)
    ambiguous = {w for ws in by_clue.values() if len(ws) > 1 for w in ws}
    return words, bank, ambiguous


def slots(grid):
    n = len(grid)
    out = []
    for d in (0, 1):
        for i in range(n):
            line = [(i, j) if d == 0 else (j, i) for j in range(n)]
            run = []
            for c in line + [None]:
                if c and grid[c[0]][c[1]] != "#":
                    run.append(c)
                else:
                    if len(run) >= 3:
                        out.append(run)
                    run = []
    return out


def count_fills(p, use_totals, cap):
    words, _, _ = vocab()
    grid = p["grid"]
    S = slots(grid)
    ans = []
    for s in S:
        w = "".join(grid[r][c] for r, c in s)
        if w in p["clues"]:
            cands = [w]
        else:
            cands = [x for x in words if len(x) == len(s) and (not use_totals or val(x) == val(w))]
        ans.append((s, cands))
    ans.sort(key=lambda a: len(a[1]))
    found = [0]
    asg = {}

    def rec(i):
        if found[0] >= cap:
            return
        if i == len(ans):
            found[0] += 1
            return
        s, cands = ans[i]
        for x in cands:
            new, ok = [], True
            for k, ch in zip(s, x):
                if k in asg:
                    if asg[k] != ch:
                        ok = False
                        break
                else:
                    new.append((k, ch))
            if ok:
                for k, ch in new:
                    asg[k] = ch
                rec(i + 1)
                for k, _ in new:
                    del asg[k]
    rec(0)
    return found[0]


def validate_puzzle(p):
    problems = []
    _, bank, ambiguous = vocab()
    grid = p["grid"]
    n = len(grid)
    if any(len(r) != n for r in grid):
        return ["grid is not square"]
    ws = ["".join(grid[r][c] for r, c in s) for s in slots(grid)]
    for w in ws:
        c, o = w in p["clues"], w in p["numOnly"]
        if c == o:
            problems.append(f"{w}: must be exactly one of clued / number-only")
    for w, clue in p["clues"].items():
        if w in ambiguous:
            problems.append(f"{w}: clue is shared with another word")
        if bank.get(w) != clue.strip().lower():
            problems.append(f"{w}: clue differs from the bank")
    if len(set(p["clues"].values())) != len(p["clues"]):
        problems.append("duplicate clue text")
    if problems:
        return problems
    if count_fills(p, True, 3) != 1:
        problems.append("totals do not leave exactly one fill")
    if count_fills(p, False, 4) < 4:
        problems.append("numbers are not needed (fewer than 4 fills without totals)")
    return problems


def main():
    bad = 0
    for path in sys.argv[1:]:
        data = json.load(open(path))
        puzzles = data["puzzles"] if isinstance(data, dict) else data
        for p in puzzles:
            probs = validate_puzzle(p)
            if probs:
                bad += 1
            print(("FAIL " if probs else "ok   ") + path, p.get("level", ""), probs or "")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
