from __future__ import annotations

from typing import Any

import pytest
import requests

from google_search_crawler.infra.config import AppConfig


class DummyResponse:
    def __init__(self, *, status_code: int, payload: dict[str, Any]) -> None:
        self.status_code = status_code
        self._payload = payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"status={self.status_code}")

    def json(self) -> dict[str, Any]:
        return self._payload


@pytest.mark.smoke
def test_vault_requires_complete_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VAULT_HOST", "https://vault.example")
    monkeypatch.delenv("VAULT_ACCOUNT", raising=False)
    monkeypatch.delenv("VAULT_PASSWORD", raising=False)
    monkeypatch.delenv("VAULT_PATH", raising=False)

    with pytest.raises(ValueError, match=r"VAULT_HOST is set; missing required env:"):
        AppConfig.from_env()


@pytest.mark.smoke
def test_vault_database_config_overrides_local_env(monkeypatch: pytest.MonkeyPatch) -> None:
    import google_search_crawler.infra.vault as vault

    monkeypatch.setenv("VAULT_HOST", "https://vault.example")
    monkeypatch.setenv("VAULT_ACCOUNT", "account")
    monkeypatch.setenv("VAULT_PASSWORD", "password")
    monkeypatch.setenv("VAULT_PATH", "webcrawler/staging")

    monkeypatch.setenv("GOOGLE_SEARCH_CRAWLER_DATABASE_URL", "postgresql://local-should-not-be-used")

    def fake_post(url: str, **kwargs: Any) -> DummyResponse:
        assert url == "https://vault.example/v1/auth/userpass/login/account"
        assert kwargs["json"] == {"password": "password"}
        assert kwargs["timeout"] == 10.0
        return DummyResponse(status_code=200, payload={"auth": {"client_token": "token"}})

    def fake_get(url: str, **kwargs: Any) -> DummyResponse:
        assert url == "https://vault.example/v1/secret/data/webcrawler/staging"
        assert kwargs["headers"]["X-Vault-Token"] == "token"
        assert kwargs["timeout"] == 10.0
        return DummyResponse(
            status_code=200,
            payload={
                "data": {
                    "data": {
                        "DB_HOST": "db.example",
                        "DB_PORT": 5432,
                        "DB_USER": "user",
                        "DB_PASS": "pass",
                        "DB_NAME": "db",
                        "DB_SSLMODE": "require",
                        "DB_SCHEMA": "webcrawler",
                    }
                }
            },
        )

    monkeypatch.setattr(vault.requests, "post", fake_post)
    monkeypatch.setattr(vault.requests, "get", fake_get)

    config = AppConfig.from_env()
    assert config.database_url != "postgresql://local-should-not-be-used"
    assert config.database_schema == "webcrawler"
