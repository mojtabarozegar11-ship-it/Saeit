"""Small fallback for django-environ's settings API.

The production cPanel selector can briefly lack the optional django-environ
package. Keeping this narrow adapter lets Django start with the same environment
values and DATABASE_URL while the normal dependency remains installed elsewhere.
"""
from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse


def _as_bool(value):
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "t", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "f", "no", "n", "off"}:
        return False
    raise ValueError(f"Invalid boolean value: {value!r}")


class Env:
    def __init__(self, **schema):
        self.schema = schema

    @staticmethod
    def read_env(path):
        path = Path(path)
        if not path.is_file():
            return
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[7:].lstrip()
            key, separator, value = line.partition("=")
            key = key.strip()
            if not separator or not key:
                continue
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
                value = value[1:-1]
            else:
                value = value.split(" #", 1)[0].rstrip()
            os.environ.setdefault(key, value)

    def __call__(self, key, default=None):
        rule = self.schema.get(key)
        cast = rule[0] if isinstance(rule, tuple) else rule
        schema_default = rule[1] if isinstance(rule, tuple) and len(rule) > 1 else None
        if key in os.environ:
            value = os.environ[key]
        elif default is not None:
            value = default
        elif schema_default is not None:
            value = schema_default
        else:
            raise KeyError(f"Environment variable {key} is not set")
        if cast is None:
            if isinstance(default, bool):
                cast = bool
            elif isinstance(default, int):
                cast = int
        if cast is bool:
            return _as_bool(value)
        if cast is not None:
            return cast(value)
        return value

    def bool(self, key, default=False):
        return _as_bool(os.environ.get(key, default))

    def int(self, key, default=0):
        return int(os.environ.get(key, default))

    def list(self, key, default=None, delimiter=","):
        value = os.environ.get(key)
        if value is None:
            return list(default or [])
        return [item.strip() for item in value.split(delimiter) if item.strip()]

    def db(self, key, default=None, conn_max_age=0, conn_health_checks=False):
        value = self(key, default=default)
        parsed = urlparse(value)
        scheme = parsed.scheme.lower()
        engines = {
            "sqlite": "django.db.backends.sqlite3",
            "postgres": "django.db.backends.postgresql",
            "postgresql": "django.db.backends.postgresql",
            "postgresql+psycopg": "django.db.backends.postgresql",
            "mysql": "django.db.backends.mysql",
            "oracle": "django.db.backends.oracle",
        }
        if scheme not in engines:
            raise ValueError(f"Unsupported DATABASE_URL scheme: {scheme!r}")
        result = {
            "ENGINE": engines[scheme],
            "NAME": "",
            "USER": unquote(parsed.username or ""),
            "PASSWORD": unquote(parsed.password or ""),
            "HOST": parsed.hostname or "",
            "PORT": str(parsed.port or ""),
            "CONN_MAX_AGE": conn_max_age,
            "CONN_HEALTH_CHECKS": conn_health_checks,
        }
        if scheme == "sqlite":
            path = unquote(parsed.path)
            result["NAME"] = path[1:] if path.startswith("//") else path
            if result["NAME"] == "/:memory:":
                result["NAME"] = ":memory:"
            return result
        result["NAME"] = unquote(parsed.path.lstrip("/"))
        query = {name: values[-1] for name, values in parse_qs(parsed.query).items()}
        if query:
            result["OPTIONS"] = query
        return result
