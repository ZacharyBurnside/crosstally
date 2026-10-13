import datetime
from .models import Completion


def compute(user, today=None):
    today = today or datetime.date.today()
    rows = list(Completion.objects.filter(user=user).values_list("date", "level", "seconds"))
    days = sorted({d for d, _, _ in rows})
    # streak: consecutive days with at least one solved puzzle, counting back from today (or yesterday)
    streak, cursor = 0, today
    dayset = set(days)
    if cursor not in dayset:
        cursor -= datetime.timedelta(days=1)
    while cursor in dayset:
        streak += 1
        cursor -= datetime.timedelta(days=1)
    best_run = run = 0
    prev = None
    for d in days:
        run = run + 1 if prev and (d - prev).days == 1 else 1
        best_run = max(best_run, run)
        prev = d
    by_level = {}
    for _, lvl, secs in rows:
        s = by_level.setdefault(str(lvl), {"solved": 0, "best_seconds": None})
        s["solved"] += 1
        s["best_seconds"] = secs if s["best_seconds"] is None else min(s["best_seconds"], secs)
    return {"solved": len(rows), "days_played": len(days), "current_streak": streak,
            "best_streak": best_run, "by_level": by_level}
