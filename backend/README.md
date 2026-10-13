# Crosstally API (Django)

Accounts (Sign in with Apple), results, streaks and leaderboards. Puzzles are plain files in `PUZZLE_DIR`
(the `daily/` folder written by `make_daily.py`); in production serve them from a CDN and treat this server's
`/api/daily/...` as a fallback.

## Run locally
```
cd backend
pip install -r requirements.txt
python3 manage.py migrate
PUZZLE_DIR=../daily python3 manage.py runserver
python3 manage.py test            # 8 tests, Apple verification is mocked
```

## Environment variables
| Name | Purpose |
|---|---|
| `SECRET_KEY` | signs session tokens. Required when `DEBUG=0`. Changing it signs everyone out. |
| `DEBUG` | `1` (default) for local use, `0` in production |
| `ALLOWED_HOSTS` | comma-separated hostnames |
| `APPLE_BUNDLE_ID` | must equal the iOS app's bundle identifier, or Apple tokens are rejected |
| `PUZZLE_DIR` | folder with `YYYY-MM-DD.json` + `index.json` |
| `DATABASE_URL` | `postgres://user:pass@host:5432/db`; SQLite if unset |
| `TOKEN_DAYS` | session lifetime, default 60 |

## Endpoints
| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `/api/health` | no | |
| GET | `/api/daily/index`, `/api/daily/<YYYY-MM-DD>` | no | cached 5 min / 1 day |
| POST | `/api/auth/apple` | no | `{identity_token}` -> `{token}` |
| GET / PATCH / DELETE | `/api/me` | yes | profile + stats / set `display_name` / delete account |
| GET / POST | `/api/completions` | yes | `{date, level, seconds, hints, checks}`; best time kept |
| GET | `/api/leaderboard/<date>/<level>` | no | top 50, named players, no hints |

Production: `gunicorn crosstally_api.wsgi` behind nginx/Caddy, or point PythonAnywhere's WSGI file at
`crosstally_api.wsgi`. Add rate limiting on the auth and completions routes.
