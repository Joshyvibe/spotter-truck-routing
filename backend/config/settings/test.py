from .base import *  # noqa: F403

DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
WEATHER_PROVIDER = "fixture"
ROUTING_PROVIDER = "fixture"
TOMTOM_API_KEY = "test-key"
LOGGING = {"version": 1, "disable_existing_loggers": False}
REST_FRAMEWORK = {
    **REST_FRAMEWORK,  # noqa: F405
    "DEFAULT_THROTTLE_RATES": {"plans": "1000/min", "geocode": "1000/min", "heatmap": "1000/min"},
}
