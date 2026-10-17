"""Production configuration, checked in a fresh interpreter per case.

settings.py runs its safety checks while it is imported, so each case imports it in a subprocess
with an explicit environment. Every variable the settings read is set (or blanked) in that
environment, so a developer's real .env can never decide the outcome: python-dotenv does not
override variables that already exist, even empty ones.
"""
import os
import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2]
STRONG_KEY = "k" * 64
VARS = (
    "DJANGO_DEBUG", "DJANGO_SECRET_KEY", "DJANGO_ALLOWED_HOSTS", "CORS_ALLOWED_ORIGINS",
    "NUM_PROXIES", "RENDER",
)

PROBE = (
    "import json, config.settings as s;"
    "print(json.dumps({'debug': s.DEBUG, 'hosts': s.ALLOWED_HOSTS, 'cors': s.CORS_ALLOWED_ORIGINS,"
    "'ssl': getattr(s, 'SECURE_SSL_REDIRECT', False), 'proxy': getattr(s, 'SECURE_PROXY_SSL_HEADER', None),"
    "'cookie': getattr(s, 'SESSION_COOKIE_SECURE', False), 'csrf': getattr(s, 'CSRF_COOKIE_SECURE', False),"
    "'exempt': getattr(s, 'SECURE_REDIRECT_EXEMPT', [])})) "
)


def load(**overrides):
    env = {k: v for k, v in os.environ.items() if k not in VARS}
    # Blank everything first: a .env value must not fill a variable the case leaves unset.
    env.update({k: "" for k in VARS})
    env["NUM_PROXIES"] = "0"  # settings read it with int(), so a blank value is not a valid input
    env.update(overrides)
    return subprocess.run(
        [sys.executable, "-c", PROBE], cwd=BACKEND, env=env, capture_output=True, text=True,
    )


def prod(**overrides):
    base = {
        "DJANGO_DEBUG": "false",
        "DJANGO_SECRET_KEY": STRONG_KEY,
        "DJANGO_ALLOWED_HOSTS": "api.example.test",
        "CORS_ALLOWED_ORIGINS": "https://app.example.test",
    }
    base.update(overrides)
    return load(**base)


def test_local_defaults_still_work_without_any_variables():
    # The documented development values. The secret key is unset, so the local default is used.
    result = load(DJANGO_DEBUG="true", DJANGO_SECRET_KEY="", DJANGO_ALLOWED_HOSTS="localhost,127.0.0.1",
                  CORS_ALLOWED_ORIGINS="http://localhost:5173")
    assert result.returncode == 0, result.stderr
    assert '"debug": true' in result.stdout
    assert '"ssl": false' in result.stdout


def test_valid_production_configuration_enables_https_hardening():
    result = prod()
    assert result.returncode == 0, result.stderr
    out = result.stdout
    assert '"debug": false' in out
    assert '"hosts": ["api.example.test"]' in out
    assert '"cors": ["https://app.example.test"]' in out
    assert '"ssl": true' in out and '"cookie": true' in out and '"csrf": true' in out
    assert '"proxy": ["HTTP_X_FORWARDED_PROTO", "https"]' in out
    assert '"exempt": ["^api/health$"]' in out


def test_production_refuses_the_insecure_default_secret_key():
    result = prod(DJANGO_SECRET_KEY="django-insecure-local-development-key-change-me")
    assert result.returncode != 0 and "DJANGO_SECRET_KEY" in result.stderr


def test_production_refuses_any_django_insecure_key_even_if_long():
    result = prod(DJANGO_SECRET_KEY="django-insecure-" + "x" * 80)
    assert result.returncode != 0 and "DJANGO_SECRET_KEY" in result.stderr


def test_production_refuses_a_missing_or_short_secret_key():
    for key in ("", "short"):
        result = prod(DJANGO_SECRET_KEY=key)
        assert result.returncode != 0 and "DJANGO_SECRET_KEY" in result.stderr


def test_production_refuses_missing_allowed_hosts():
    result = prod(DJANGO_ALLOWED_HOSTS="")
    assert result.returncode != 0 and "DJANGO_ALLOWED_HOSTS" in result.stderr


def test_production_refuses_missing_cors_origins_instead_of_defaulting_to_localhost():
    result = prod(CORS_ALLOWED_ORIGINS="")
    assert result.returncode != 0 and "CORS_ALLOWED_ORIGINS" in result.stderr


def test_debug_on_render_is_refused():
    result = load(RENDER="true", DJANGO_DEBUG="true", DJANGO_SECRET_KEY=STRONG_KEY,
                  DJANGO_ALLOWED_HOSTS="x.test", CORS_ALLOWED_ORIGINS="https://a.test")
    assert result.returncode != 0 and "DJANGO_DEBUG" in result.stderr


def test_render_with_debug_false_starts():
    result = prod(RENDER="true")
    assert result.returncode == 0, result.stderr
