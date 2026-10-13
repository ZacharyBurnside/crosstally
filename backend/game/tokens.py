"""Our own session tokens (HS256 JWT) handed out after Apple sign-in."""
import datetime
import jwt
from django.conf import settings
from .models import AppUser


def issue(user):
    now = datetime.datetime.now(datetime.timezone.utc)
    return jwt.encode({"uid": user.id, "iat": now, "exp": now + datetime.timedelta(days=settings.TOKEN_DAYS)},
                      settings.SECRET_KEY, algorithm="HS256")


def user_from_request(request):
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return None
    try:
        data = jwt.decode(header[7:], settings.SECRET_KEY, algorithms=["HS256"])
        return AppUser.objects.filter(id=data["uid"]).first()
    except Exception:
        return None
