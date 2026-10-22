from .base import *  # noqa: F403
from .base import SECRET_KEY

if SECRET_KEY.startswith("dev-"):
    raise RuntimeError("DJANGO_SECRET_KEY must be set in production")

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = False  # the host's edge terminates TLS and only serves HTTPS
SECURE_HSTS_SECONDS = 31536000
SECURE_CONTENT_TYPE_NOSNIFF = True

# The host's edge proxy appends the client IP to X-Forwarded-For; throttles key on it.
REST_FRAMEWORK = {**REST_FRAMEWORK, "NUM_PROXIES": 1}  # noqa: F405
