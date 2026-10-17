
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR.parent / ".env")

# Read configuration from environment variables.
DEBUG = os.environ.get("DJANGO_DEBUG", "true").strip().lower() in {
    "1", "true", "yes", "on"
}

SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "django-insecure-local-development-key-change-me",
)

# Render sets RENDER=true on every service. The local default for DJANGO_DEBUG is "true", so a
# forgotten variable there would silently leave debug on in production: refuse to start instead.
if os.environ.get("RENDER", "").strip().lower() == "true" and DEBUG:
    raise RuntimeError("DJANGO_DEBUG must be false on Render.")

MIN_SECRET_KEY_LENGTH = 50  # Django's own deployment check (security.W009) uses the same bound

if not DEBUG and (
    SECRET_KEY.startswith("django-insecure-")
    or len(SECRET_KEY) < MIN_SECRET_KEY_LENGTH
):
    raise RuntimeError(
        "Set a strong DJANGO_SECRET_KEY in production "
        f"(at least {MIN_SECRET_KEY_LENGTH} characters)."
    )


def env_list(name: str, default: str = "") -> list[str]:
    return [
        value.strip()
        for value in os.environ.get(name, default).split(",")
        if value.strip()
    ]


ALLOWED_HOSTS = env_list(
    "DJANGO_ALLOWED_HOSTS",
    "localhost,127.0.0.1",
)

if not DEBUG and not ALLOWED_HOSTS:
    raise RuntimeError("Set DJANGO_ALLOWED_HOSTS in production.")



# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    "rest_framework",
    "corsheaders",
    "trips",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.gzip.GZipMiddleware",
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',

]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'


# Database
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}


# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/

STATIC_URL = 'static/'

# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
# The localhost default exists for development only. In production the deployed frontend's origin
# must be listed explicitly, otherwise every browser request would be blocked without a clear cause.
CORS_ALLOWED_ORIGINS = env_list(
    "CORS_ALLOWED_ORIGINS",
    "http://localhost:5173" if DEBUG else "",
)

if not DEBUG and not CORS_ALLOWED_ORIGINS:
    raise RuntimeError("Set CORS_ALLOWED_ORIGINS in production.")

if not DEBUG:
    SECURE_SSL_REDIRECT = True
    # A platform health probe may arrive over plain HTTP; a redirect there could mark the service
    # unhealthy. The endpoint returns only {"status": "ok"}, so exempting it exposes nothing.
    SECURE_REDIRECT_EXEMPT = [r"^api/health$"]
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"


# Per-client limits on POST /api/trips/analyze (see trips/throttling.py for the reasoning).
# Change them without code through ANALYZE_RATE_BURST / ANALYZE_RATE_HOUR, e.g. "20/min".
ANALYZE_THROTTLE_RATES = {
    "analyze_burst": os.environ.get("ANALYZE_RATE_BURST", "10/min"),
    "analyze_hour": os.environ.get("ANALYZE_RATE_HOUR", "30/hour"),
}

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": [],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "UNAUTHENTICATED_USER": None,
    "EXCEPTION_HANDLER": "trips.throttling.api_exception_handler",
    # How many proxies sit in front of the app. 0 (local) means "use the connecting address".
    # Behind a host's proxy set NUM_PROXIES=1 so the real client address is read from
    # X-Forwarded-For; otherwise every visitor would share one throttle bucket.
    "NUM_PROXIES": int(os.environ.get("NUM_PROXIES", "0")),
}