# Crosstally: daily cycle, accounts and scaling

## 1. What runs where

```
 GitHub Actions (weekly cron)            Static hosting / CDN                 iPhone app
 ┌───────────────────────────┐   files   ┌──────────────────────┐   GET      ┌─────────────────┐
 │ lint_bank.py              │ ───────▶  │ daily/2026-10-14.json │ ◀───────── │ DailyService    │
 │ make_daily.py (4 levels)  │           │ daily/index.json      │            │ cache + bundled │
 │ validate.py (re-check)    │           └──────────────────────┘            │ fallback        │
 └───────────────────────────┘                                                │                 │
                                          Django API (optional accounts)      │ AuthService     │
                                          ┌──────────────────────┐   POST     │ Sign in with    │
                                          │ /api/auth/apple       │ ◀───────── │ Apple, results  │
                                          │ /api/completions      │            │ queue + sync    │
                                          │ /api/me, /leaderboard │            └─────────────────┘
                                          └──────────────────────┘
```

Puzzles are **files**, not database rows. They are generated ahead of time, never change once published,
and every player downloads the same four per day. That is why the puzzle side costs almost nothing at any scale.
Only the account features (streaks, leaderboards) need a server that runs code.

## 2. The daily cycle, step by step

1. **Bank**: `clue_bank.txt` holds `WORD|clue` lines (3,367 words today). `lint_bank.py` rejects clues that
   leak the answer, duplicates and malformed lines. Words that share an identical clue are never shown as
   clued answers (they stay available as number-only answers).
2. **Generate** (`make_daily.py --start <today> --days 30`): for each date that has no file yet it
   - seeds the generator from the date (re-running reproduces the same day),
   - builds symmetric 5x5 grids from bank words only, then picks which answers lose their clue,
   - keeps only puzzles where the totals leave exactly one fill among ~10,000 words, and where several fills
     exist without the totals (so neither mechanic solves it alone),
   - sorts candidates into **level 1 to 4** by how many cells only the numbers can reveal and how many
     answers are number-only, and keeps one puzzle per level,
   - avoids any answer used in the last 7 days and any clued answer used in the last 30 days.
3. **Validate** (`validate.py`): a second, separate solver re-checks every puzzle before it is written and again
   in CI. A puzzle that fails is thrown away and regenerated.
4. **Publish**: files are committed (GitHub Pages / Django static) or synced to S3 behind CloudFront
   (the commented step in `.github/workflows/daily-puzzles.yml`). Day files are immutable, so they cache for a year;
   only `index.json` has a short cache.
5. **App**: on launch it asks for today's file (local date), caches it on disk, and falls back to the bundled
   puzzles if offline. Players can step back through earlier days.
6. **Safety margin**: the job runs weekly and always keeps 30 days ahead, so a failed run does not break any day.
   Add an alert (Actions failure email is enough) and check `daily/index.json` has dates 20+ days out.

Run it by hand: `python3 make_daily.py --start 2026-10-14 --days 7 --out-dir daily`.
Time: about 1 to 6 minutes per day on one CPU core (level 4 is the slow one, and it slows as the no-repeat window fills), so the first 30 days take 1 to 3 hours and a weekly top-up of 7 days takes 10 to 40 minutes.

## 3. Word bank capacity

- 3,367 clued words (321 three-letter, 878 four, 1,016 five, 1,152 six).
- Four puzzles a day use about 40 answer slots a day, about 14,600 a year: on average each word appears about
  4 times a year, with the 7 and 30 day gaps above preventing back-to-back repeats.
- Weak spot: three-letter words. There are only a few hundred common ones, so they repeat most (tens of times a
  year each). Mitigation, in order of value: write 2 to 3 different clues per word and rotate them; add more
  short words; accept that short repeats are normal in crosswords.
- To go from 3k to 10k words: bulk-draft clues with an LLM from a candidate list (`wordfreq` zipf >= 3.3,
  length 3 to 6, names/abbreviations removed), then run `lint_bank.py` and spot-check a sample of ~5%.
  The validator's vocabulary grows automatically with the bank.

## 4. Accounts

- The game works as a **guest**. Nothing requires an account.
- **Sign in with Apple** is optional and gives: streaks across devices, saved history, leaderboards.
  Why Apple: no passwords to store or reset, no email verification, one tap, and App Store rules require it
  if you add any other third-party login.
- Flow: app gets an identity token from Apple -> `POST /api/auth/apple` -> server verifies the signature against
  Apple's public keys and the app's bundle id -> returns its own 60-day session token (kept in the Keychain).
- Results are recorded locally first and queued; they sync when signed in and online, so offline play is never lost.
- Server rules: one result per user per puzzle, the best time is kept, leaderboard excludes hint users and
  anyone without a display name.
- **Account deletion** (`DELETE /api/me`) is implemented because Apple requires it for apps with accounts.

## 5. Scaling checklist

| Stage | What to do |
|---|---|
| 0 to 5k users | One small server (PythonAnywhere / a $5 VPS) running Django + SQLite, puzzles served from GitHub Pages. |
| 5k to 100k | Move Django to Postgres (`DATABASE_URL`), put puzzles on S3 + CloudFront, run gunicorn with a few workers. |
| 100k+ | Cache `/api/leaderboard` (30 s), put the API behind a CDN/WAF with rate limiting, add read replica if needed. |

The expensive path is the write path (`POST /api/completions`): it is one small upsert per solved puzzle, indexed
on (user, date, level), so even 100k daily players is a few requests per second on average.

Before launch:
- Set `SECRET_KEY`, `DEBUG=0`, `ALLOWED_HOSTS`, `APPLE_BUNDLE_ID` environment variables (see `backend/README.md`).
- Add rate limiting on `/api/auth/apple` and `/api/completions` (nginx `limit_req`, Cloudflare, or django-ratelimit).
- Privacy policy URL + App Store privacy labels (data collected: Apple user id, optional email, gameplay results).
- Sign in with Apple needs the capability in a real Xcode project with a paid developer team.

## 6. What has and has not been tested

- Tested: bank lint, generator at four levels, validator on every shipped puzzle, backend unit tests (mocked Apple
  verification).
- Not tested: the Swift app has never been compiled by the author of this code; the Apple token check has not run
  against Apple's live keys; no load test; puzzle fun and difficulty feel have not been playtested.
- "Exactly one fill" is measured against ~10,000 common words, not a full dictionary.
