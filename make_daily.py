#!/usr/bin/env python3
"""Generate the daily Crosstally puzzles (4 levels per date).

    python3 make_daily.py --start 2026-10-30 --days 60 --out-dir daily

Idempotent: dates that already have a file are skipped.
Variety rules: no answer used in the last 7 days, no clued answer in the last 30 days, and no answer
shared between the four puzzles of one day (levels are generated one at a time).
"""
import argparse, datetime, json, os, sys, time
import crosstally_gen as g
from validate import validate_puzzle

LEVELS = (1, 2, 3, 4)
SEARCH_ORDER = (1, 4, 3, 2)   # rarest level first, while the pool of unused words is largest
ATTEMPTS = 12                 # reseeds per level before giving up on the date


def load_day(path):
    try:
        return json.load(open(path))
    except Exception:
        return None


def recent_words(out_dir, day, any_days=3, clued_days=14):
    avoid = set()
    for back in range(1, clued_days + 1):
        d = day - datetime.timedelta(days=back)
        data = load_day(os.path.join(out_dir, d.isoformat() + ".json"))
        if not data:
            continue
        for p in data["puzzles"]:
            avoid |= set(p["clues"])
            if back <= any_days:
                avoid |= set(p["numOnly"])
    return avoid


def make_day(day, out_dir, size, salt, tlimit, verbose):
    seed = int(day.strftime("%Y%m%d")) * 1000 + salt
    avoid = recent_words(out_dir, day)
    have = {}
    for lvl in SEARCH_ORDER:
        for attempt in range(ATTEMPTS):
            found = g.generate(size, 1, seed + lvl * 104729 + attempt * 7919, tlimit=tlimit,
                               max_patterns=900, verbose=verbose, need={lvl: 1}, avoid_words=avoid)
            for p in found:
                if p["meta"]["level"] != lvl:
                    continue
                problems = validate_puzzle(p)
                if problems:
                    print(f"  rejected level {lvl}: {problems}", file=sys.stderr)
                    continue
                have[lvl] = {"level": lvl, "size": size, "grid": p["grid"], "numOnly": p["numOnly"],
                             "clues": p["clues"], "meta": p["meta"]}
                avoid |= set(p["clues"]) | set(p["numOnly"])   # never reuse an answer inside one day
                break
            if lvl in have:
                break
        if lvl not in have:
            return None
    return {"date": day.isoformat(), "version": 1, "puzzles": [have[l] for l in LEVELS]}


def write_index(out_dir):
    dates = sorted(f[:-5] for f in os.listdir(out_dir) if len(f) == 15 and f.endswith(".json"))
    tmp = os.path.join(out_dir, "index.json.tmp")
    json.dump({"dates": dates, "updated": datetime.datetime.utcnow().isoformat() + "Z"}, open(tmp, "w"))
    os.replace(tmp, os.path.join(out_dir, "index.json"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default=datetime.date.today().isoformat())
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--out-dir", default="daily")
    ap.add_argument("--size", type=int, default=5, choices=[5, 6])
    ap.add_argument("--salt", type=int, default=0, help="change to get a different set for the same dates")
    ap.add_argument("--time-limit", type=float, default=6.0)
    ap.add_argument("-q", "--quiet", action="store_true")
    a = ap.parse_args()
    os.makedirs(a.out_dir, exist_ok=True)
    start = datetime.date.fromisoformat(a.start)
    made = failed = 0
    for i in range(a.days):
        day = start + datetime.timedelta(days=i)
        path = os.path.join(a.out_dir, day.isoformat() + ".json")
        if os.path.exists(path):
            continue
        t0 = time.time()
        data = make_day(day, a.out_dir, a.size, a.salt, a.time_limit, not a.quiet)
        if not data:
            print(f"{day}: FAILED to make all four levels", file=sys.stderr)
            failed += 1
            continue
        tmp = path + ".tmp"
        json.dump(data, open(tmp, "w"), indent=1)
        os.replace(tmp, path)
        write_index(a.out_dir)
        made += 1
        print(f"{day}: wrote 4 puzzles in {time.time() - t0:.0f}s", file=sys.stderr)
    write_index(a.out_dir)
    print(f"done: {made} made, {failed} failed", file=sys.stderr)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
