"""Lint a clue bank: python3 lint_bank.py clue_bank.txt  (exit 1 on errors)"""
import sys, re, collections
path = sys.argv[1] if len(sys.argv) > 1 else "clue_bank.txt"
seen, clues, errs, warns = {}, collections.defaultdict(list), [], []
for n, line in enumerate(open(path, encoding="utf8"), 1):
    line = line.rstrip("\n")
    if not line.strip() or line.startswith("#"): continue
    if "|" not in line: errs.append(f"{n}: no '|'"); continue
    w, c = line.split("|", 1); c = c.strip()
    if not re.fullmatch(r"[A-Z]{3,6}", w): errs.append(f"{n}: bad word {w!r}"); continue
    if w in seen: errs.append(f"{n}: duplicate {w} (first on line {seen[w]})"); continue
    seen[w] = n
    if len(c) < 3 or len(c) > 60: errs.append(f"{n}: {w} clue length {len(c)}")
    low = c.lower()
    wl = w.lower()
    toks = re.findall(r"[a-z]+", low)
    leak = [t for t in toks if t == wl or (len(t) >= 4 and (t.startswith(wl) or wl.startswith(t)))]
    if leak:
        errs.append(f"{n}: {w} clue leaks the answer ({leak[0]}): {c}")
    clues[low].append(w)
for c, ws in clues.items():
    if len(ws) > 1: warns.append(f"same clue for {ws}: {c}")
for e in errs: print("ERROR", e)
for w in warns: print("warn ", w)
print(f"{len(seen)} words, {len(errs)} errors, {len(warns)} warnings")
sys.exit(1 if errs else 0)
