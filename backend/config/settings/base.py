"""Settings shared by every environment. Secrets and hosts come from the environment."""

import os
from pathlib import Path

import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent.parent


def env_list(name: str, default: str = "") -> list[str]:
    return [v.strip() for v in os.environ.get(name, default).split(",") if v.strip()]


SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-insecure-key-change-me")
DEBUG = False
ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "localhost,127.0.0.1")

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "corsheaders",
    "rest_framework",
    "routing",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.gzip.GZipMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "routing.api.middleware.RequestIdMiddleware",
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": dj_database_url.config(
        default="postgres://spotter:spotter@localhost:5432/spotter",
        conn_max_age=60,
        conn_health_checks=True,
    )
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REDIS_URL = os.environ.get("REDIS_URL", "")
if REDIS_URL:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": REDIS_URL,
            "TIMEOUT": 600,
        }
    }
else:
    # Fallback when no Redis is configured (docs/DESIGN.md §8).
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}

USE_TZ = True
TIME_ZONE = "UTC"
LANGUAGE_CODE = "en-us"
DATA_UPLOAD_MAX_MEMORY_SIZE = 16 * 1024  # request bodies are tiny JSON

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [],  # public API, no session/CSRF (out of scope: auth)
    "DEFAULT_PERMISSION_CLASSES": [],
    "UNAUTHENTICATED_USER": None,
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    "EXCEPTION_HANDLER": "routing.api.errors.exception_handler",
    "DEFAULT_THROTTLE_RATES": {
        "plans": "20/hour",
        "geocode": "60/min",
        "heatmap": "60/hour",
    },
}

CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS", "http://localhost:5173")
CORS_EXPOSE_HEADERS = ["X-Request-ID", "Retry-After", "Location"]

# Providers (swap with one env var; docs/DESIGN.md §2)
ROUTING_PROVIDER = os.environ.get("ROUTING_PROVIDER", "tomtom")  # tomtom | osrm
WEATHER_PROVIDER = os.environ.get("WEATHER_PROVIDER", "openmeteo")  # openmeteo | fixture
TOMTOM_API_KEY = os.environ.get("TOMTOM_API_KEY", "")
# TomTom wants gross vehicle weight; the brief's rules use load weight (TECHNICAL_DESIGN R7).
TRUCK_TARE_LB = 35_000

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"json": {"()": "routing.logging.JsonFormatter"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "json"}},
    "root": {"handlers": ["console"], "level": "INFO"},
    # httpx logs full request URLs at INFO, and TomTom's API key is a query parameter.
    # Our own "upstream call" log line records service/status/ms without the URL.
    "loggers": {
        "httpx": {"level": "WARNING"},
        "httpcore": {"level": "WARNING"},
    },
}
