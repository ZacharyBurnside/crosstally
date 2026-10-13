"""Verify a Sign in with Apple identity token (a JWT signed by Apple)."""
import jwt
from django.conf import settings

APPLE_KEYS = "https://appleid.apple.com/auth/keys"
_jwks = jwt.PyJWKClient(APPLE_KEYS, cache_keys=True)


class AppleAuthError(Exception):
    pass


def verify_identity_token(token):
    """Return the token's claims (including 'sub') or raise AppleAuthError."""
    try:
        key = _jwks.get_signing_key_from_jwt(token).key
        return jwt.decode(token, key, algorithms=["RS256"], audience=settings.APPLE_BUNDLE_ID,
                          issuer="https://appleid.apple.com")
    except Exception as e:                       # any failure means "do not trust this token"
        raise AppleAuthError(str(e))
