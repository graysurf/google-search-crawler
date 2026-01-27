"""Minimal Hashicorp Vault client for configuration fetching (KV v2 + userpass)."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any

import requests
from psycopg.conninfo import make_conninfo


logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class VaultSettings:
    host: str
    account: str
    password: str
    path: str
    timeout_seconds: float = 10.0


def load_database_config_from_vault_env() -> tuple[str, str | None]:
    settings = _settings_from_env()
    secret_data = _fetch_kv2_secret(settings)
    database_url = _resolve_database_url(secret_data)
    database_schema = _resolve_database_schema(secret_data)
    return database_url, database_schema


def _settings_from_env() -> VaultSettings:
    host = (os.environ.get("VAULT_HOST") or "").strip()
    if not host:
        raise ValueError("VAULT_HOST is not set")

    account = (os.environ.get("VAULT_ACCOUNT") or "").strip()
    password = os.environ.get("VAULT_PASSWORD") or ""
    path = (os.environ.get("VAULT_PATH") or "").strip()

    missing: list[str] = []
    if not account:
        missing.append("VAULT_ACCOUNT")
    if not password:
        missing.append("VAULT_PASSWORD")
    if not path:
        missing.append("VAULT_PATH")
    if missing:
        missing_display = ", ".join(missing)
        raise ValueError(f"VAULT_HOST is set; missing required env: {missing_display}")

    return VaultSettings(
        host=host.rstrip("/"),
        account=account,
        password=password,
        path=path.lstrip("/"),
    )


def _fetch_kv2_secret(settings: VaultSettings) -> dict[str, Any]:
    token = _login_userpass(settings)
    data = _get_secret_data(settings, token)
    logger.debug("vault secret loaded path=%s keys=%s", settings.path, sorted(data.keys()))
    return data


def _login_userpass(settings: VaultSettings) -> str:
    url = f"{settings.host}/v1/auth/userpass/login/{settings.account}"
    try:
        resp = requests.post(url, json={"password": settings.password}, timeout=settings.timeout_seconds)
    except requests.RequestException as exc:
        raise RuntimeError("failed to connect to vault for login") from exc

    payload = _parse_vault_payload(resp, context="login")
    auth = payload.get("auth")
    if not isinstance(auth, dict):
        raise RuntimeError("vault login response missing auth")

    token = auth.get("client_token")
    if not isinstance(token, str) or not token:
        raise RuntimeError("vault login response missing client_token")
    return token


def _get_secret_data(settings: VaultSettings, token: str) -> dict[str, Any]:
    url = f"{settings.host}/v1/secret/data/{settings.path}"
    try:
        resp = requests.get(
            url,
            headers={"X-Vault-Token": token},
            timeout=settings.timeout_seconds,
        )
    except requests.RequestException as exc:
        raise RuntimeError("failed to connect to vault for secret fetch") from exc

    if resp.status_code == 404:
        raise RuntimeError(f"vault secret not found: secret/data/{settings.path}")

    payload = _parse_vault_payload(resp, context="get_secret")
    data = payload.get("data")
    if not isinstance(data, dict):
        raise RuntimeError("vault secret response missing data")

    secret = data.get("data")
    if not isinstance(secret, dict):
        raise RuntimeError("vault secret response missing data.data")

    return secret


def _parse_vault_payload(resp: requests.Response, *, context: str) -> dict[str, Any]:
    try:
        resp.raise_for_status()
    except requests.HTTPError as exc:
        raise RuntimeError(f"vault {context} failed status={resp.status_code}") from exc

    try:
        payload = resp.json()
    except ValueError as exc:
        raise RuntimeError(f"vault {context} returned invalid JSON") from exc

    if not isinstance(payload, dict):
        raise RuntimeError(f"vault {context} returned non-object JSON")

    errors = payload.get("errors")
    if isinstance(errors, list) and errors:
        errors_display = ", ".join(str(item) for item in errors)
        raise RuntimeError(f"vault {context} error: {errors_display}")

    return payload


def _resolve_database_url(secret_data: dict[str, Any]) -> str:
    explicit_url = _get_secret_string(secret_data, "GOOGLE_SEARCH_CRAWLER_DATABASE_URL") or _get_secret_string(
        secret_data, "WEB_CRAWLER_DATABASE_URL"
    )
    if explicit_url:
        return explicit_url

    host = _get_secret_string(secret_data, "DB_HOST")
    user = _get_secret_string(secret_data, "DB_USER")
    password = _get_secret_string(secret_data, "DB_PASS")
    database = _get_secret_string(secret_data, "DB_NAME")
    port = _get_secret_string(secret_data, "DB_PORT") or "5432"
    sslmode = _get_secret_string(secret_data, "DB_SSLMODE")

    missing: list[str] = []
    if not host:
        missing.append("DB_HOST")
    if not user:
        missing.append("DB_USER")
    if not password:
        missing.append("DB_PASS")
    if not database:
        missing.append("DB_NAME")
    if missing:
        missing_display = ", ".join(missing)
        raise RuntimeError(f"vault secret missing required DB fields: {missing_display}")

    assert host is not None
    assert user is not None
    assert password is not None
    assert database is not None

    kwargs: dict[str, str] = {
        "host": host,
        "port": port,
        "user": user,
        "password": password,
        "dbname": database,
    }
    if sslmode:
        kwargs["sslmode"] = sslmode

    return make_conninfo(**kwargs)


def _resolve_database_schema(secret_data: dict[str, Any]) -> str | None:
    return (
        _get_secret_string(secret_data, "GOOGLE_SEARCH_CRAWLER_DB_SCHEMA")
        or _get_secret_string(secret_data, "WEB_CRAWLER_DB_SCHEMA")
        or _get_secret_string(secret_data, "DB_SCHEMA")
    )


def _get_secret_string(secret_data: dict[str, Any], key: str) -> str | None:
    value = secret_data.get(key)
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        return text or None
    return str(value)
