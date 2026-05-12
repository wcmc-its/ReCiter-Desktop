"""Tests for the shared-secret API token (api.auth)."""
import os
import stat
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.auth import (
    TOKEN_HEADER,
    TokenAuthMiddleware,
    load_or_create_token,
    reset_cache_for_tests,
)


@pytest.fixture
def token_path(tmp_path: Path) -> Path:
    reset_cache_for_tests()
    return tmp_path / "api-token"


def _make_app(token: str) -> TestClient:
    app = FastAPI()
    app.add_middleware(TokenAuthMiddleware, token=token)

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    @app.get("/api/secret")
    def secret():
        return {"data": "private"}

    return TestClient(app)


def test_load_or_create_token_generates_and_persists(token_path: Path):
    assert not token_path.exists()
    token = load_or_create_token(token_path)
    assert token
    assert token_path.exists()
    assert token_path.read_text().strip() == token


def test_load_or_create_token_reuses_existing(token_path: Path):
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text("abc123-existing")
    reset_cache_for_tests()
    token = load_or_create_token(token_path)
    assert token == "abc123-existing"


def test_token_file_is_chmod_600_on_unix(token_path: Path):
    load_or_create_token(token_path)
    if os.name == "posix":
        mode = stat.S_IMODE(token_path.stat().st_mode)
        assert mode == 0o600


def test_request_without_token_is_rejected():
    client = _make_app("the-token")
    res = client.get("/api/secret")
    assert res.status_code == 401


def test_request_with_wrong_token_is_rejected():
    client = _make_app("the-token")
    res = client.get("/api/secret", headers={TOKEN_HEADER: "wrong"})
    assert res.status_code == 401


def test_request_with_correct_token_passes():
    client = _make_app("the-token")
    res = client.get("/api/secret", headers={TOKEN_HEADER: "the-token"})
    assert res.status_code == 200
    assert res.json() == {"data": "private"}


def test_health_is_exempt_from_token_check():
    client = _make_app("the-token")
    res = client.get("/api/health")
    assert res.status_code == 200


def test_options_preflight_is_exempt():
    client = _make_app("the-token")
    res = client.options("/api/secret")
    # FastAPI returns 405 by default for OPTIONS without CORS middleware,
    # but importantly NOT 401 — the auth middleware lets OPTIONS through.
    assert res.status_code != 401
