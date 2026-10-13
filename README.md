# Crosstally

Crossword where some answers have a clue and the rest only a letter-value total (A=1 ... Z=26).

```
clue_bank.txt            3,367 WORD|clue lines
crosstally_gen.py        puzzle generator (bank-only fills, proves the totals leave one fill)
make_daily.py            4 puzzles (levels 1-4) per date -> daily/YYYY-MM-DD.json
validate.py              independent re-check of every puzzle
lint_bank.py             clue bank checks
daily/                   generated puzzle files (+ index.json)
backend/                 Django API: Sign in with Apple, results, streaks, leaderboards
Crosstally.swiftpm/      the iPhone app (open in Xcode 15+)
.github/workflows/       weekly job that keeps 60 days of puzzles ahead
ARCHITECTURE.md          how the daily cycle, accounts and scaling fit together
```

Quick start
```
pip install -r requirements-generator.txt
python3 lint_bank.py clue_bank.txt
python3 make_daily.py --start 2026-10-14 --days 7 --out-dir daily
python3 validate.py daily/2*.json
cd backend && pip install -r requirements.txt && python3 manage.py test
```
