import datetime
import json
import re
from django.conf import settings
from django.db import IntegrityError
from django.http import JsonResponse, HttpResponse, HttpResponseNotAllowed
from django.views.decorators.csrf import csrf_exempt

from . import apple, stats, tokens
from .models import AppUser, Completion

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _body(request):
    try:
        return json.loads(request.body or b"{}")
    except ValueError:
        return None


def _err(msg, status=400):
    return JsonResponse({"error": msg}, status=status)


def health(request):
    return JsonResponse({"ok": True})


# ---------------------------------------------------------------- puzzles (static files; put a CDN in front)
def _puzzle_file(name):
    path = (settings.PUZZLE_DIR / name).resolve()
    if settings.PUZZLE_DIR.resolve() not in path.parents or not path.exists():
        return None
    return path


def _serve(name, max_age):
    path = _puzzle_file(name)
    if not path:
        return _err("not found", 404)
    resp = HttpResponse(path.read_bytes(), content_type="application/json")
    resp["Cache-Control"] = f"public, max-age={max_age}"
    return resp


def daily_index(request):
    return _serve("index.json", 300)


def daily(request, day):
    if not DATE_RE.match(day):
        return _err("bad date")
    return _serve(day + ".json", 86400)    # a day's puzzles never change once published


# ---------------------------------------------------------------- auth
@csrf_exempt
def auth_apple(request):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    data = _body(request)
    if not data or not data.get("identity_token"):
        return _err("identity_token required")
    try:
        claims = apple.verify_identity_token(data["identity_token"])
    except apple.AppleAuthError:
        return _err("invalid Apple token", 401)
    user, created = AppUser.objects.get_or_create(apple_sub=claims["sub"],
                                                  defaults={"email": claims.get("email", "")})
    return JsonResponse({"token": tokens.issue(user), "new_user": created,
                         "profile": {"display_name": user.display_name}})


# ---------------------------------------------------------------- profile
@csrf_exempt
def me(request):
    user = tokens.user_from_request(request)
    if not user:
        return _err("sign in required", 401)
    if request.method == "GET":
        return JsonResponse({"display_name": user.display_name, "stats": stats.compute(user)})
    if request.method == "PATCH":
        data = _body(request) or {}
        name = str(data.get("display_name", "")).strip()[:40]
        user.display_name = name
        user.save(update_fields=["display_name"])
        return JsonResponse({"display_name": user.display_name})
    if request.method == "DELETE":          # App Store rule: apps with sign-in must let users delete the account
        user.delete()
        return JsonResponse({"deleted": True})
    return HttpResponseNotAllowed(["GET", "PATCH", "DELETE"])


# ---------------------------------------------------------------- results
@csrf_exempt
def completions(request):
    user = tokens.user_from_request(request)
    if not user:
        return _err("sign in required", 401)
    if request.method == "GET":
        since = request.GET.get("since")
        qs = Completion.objects.filter(user=user)
        if since and DATE_RE.match(since):
            qs = qs.filter(date__gte=since)
        rows = [{"date": c.date.isoformat(), "level": c.level, "seconds": c.seconds,
                 "hints": c.hints, "checks": c.checks} for c in qs.order_by("date", "level")]
        return JsonResponse({"completions": rows, "stats": stats.compute(user)})
    if request.method != "POST":
        return HttpResponseNotAllowed(["GET", "POST"])
    data = _body(request)
    try:
        day = datetime.date.fromisoformat(str(data["date"]))
        level, seconds = int(data["level"]), int(data["seconds"])
        hints, checks = int(data.get("hints", 0)), int(data.get("checks", 0))
    except Exception:
        return _err("date, level, seconds required")
    if not (1 <= level <= 4) or not (0 < seconds < 24 * 3600) or min(hints, checks) < 0:
        return _err("values out of range")
    if day > datetime.date.today() + datetime.timedelta(days=1):
        return _err("date is in the future")
    obj, created = Completion.objects.get_or_create(
        user=user, date=day, level=level,
        defaults={"seconds": seconds, "hints": min(hints, 255), "checks": min(checks, 255)})
    if not created and seconds < obj.seconds:      # keep the better time; replays never make it worse
        obj.seconds, obj.hints, obj.checks = seconds, min(hints, 255), min(checks, 255)
        obj.save()
    return JsonResponse({"recorded": True, "first_time": created, "stats": stats.compute(user)})


def leaderboard(request, day, level):
    if not DATE_RE.match(day) or not 1 <= level <= 4:
        return _err("bad request")
    rows = (Completion.objects.filter(date=day, level=level, hints=0)
            .exclude(user__display_name="").select_related("user").order_by("seconds")[:50])
    return JsonResponse({"date": day, "level": level,
                         "entries": [{"name": c.user.display_name, "seconds": c.seconds} for c in rows]})
