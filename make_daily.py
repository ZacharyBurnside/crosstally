"""Pre-generate daily puzzles: four per date, level 1 (easiest) to 4 (hardest).

    python3 make_daily.py --start 2026-10-14 --days 30 --out-dir daily

Idempotent: dates that already have a file are skipped, so a scheduled job can simply call it with
"--start today --days 60" and only the missing dates are made. Output per date:

    daily/2026-10-14.json   {"date": ..., "version": 1, "puzzles": [{"level": 1, "grid": ..., ...}, x4]}
    daily/index.json        {"dates": ["2026-10-14", ...], "updated": ...}

Variety rules: no answer used in the last 7 days, no clued answer in the last 30 days, and a grid never repeats.
Every puzzle is re-checked by validate.py before it is written.
"""
import argparse, datetime, json, os, sys, time
import crosstally_gen as g
from validate import validate_puzzle

LEVELS = (1, 2, 3, 4)


def load_day(path):
    try:
        return json.load(open(path))
    except Exception:
        return None


def recent_words(out_dir, day, any_days=7, clued_days=30):
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
    for attempt in range(6):                       # reseed if validation rejects something
        need = {l: 1 for l in LEVELS if l not in have}
        if not need:
            break
        found = g.generate(size, len(need), seed + attempt * 7919, tlimit=tlimit, max_patterns=900,
                           verbose=verbose, need=need, avoid_words=avoid)
        for p in found:
            lvl = p["meta"]["level"]
            if lvl in have:
                continue
            problems = validate_puzzle(p)
            if problems:
                print(f"  rejected level {lvl}: {problems}", file=sys.stderr)
                continue
            have[lvl] = {"level": lvl, "size": size, "grid": p["grid"], "numOnly": p["numOnly"],
                         "clues": p["clues"], "meta": p["meta"]}
            avoid |= set(p["clues"]) | set(p["numOnly"])   # never reuse an answer inside one day
    if len(have) < len(LEVELS):
        return None
    return {"date": day.isoformat(), "version": 1, "puzzles": [have[l] for l in LEVELS]}


def write_index(out_dir):
    dates = sorted(f[:-5] for f in os.listdir(out_dir) if len(f) == 15 and f.endswith(".json"))
    tmp = os.path.join(out_dir, "index.json.tmp")
    json.dump({"dates": dates, "updated": datetime.datetime.now(datetime.timezone.utc).isoformat()}, open(tmp, "w"))
    os.replace(tmp, os.path.join(out_dir, "index.json"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default=datetime.date.today().isoformat())
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--out-dir", default="daily")
    ap.add_argument("--size", type=int, default=5, choices=[5, 6])
    ap.add_argument("--salt", type=int, default=0, help="change to get a different set for the same dates")
    ap.add_argument("--time-limit", type=float, default=2.0)
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
