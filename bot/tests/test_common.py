from fastapi import HTTPException

from app import common


def test_require_internal_token_allows_when_disabled(monkeypatch):
    monkeypatch.setenv("BOT_REQUIRE_INTERNAL_TOKEN", "0")
    monkeypatch.setenv("INTERNAL_TOKEN", "change-me")
    common._INTERNAL_TOKEN_WARNING_EMITTED = False

    assert common.require_internal_token(None) is None


def test_require_internal_token_rejects_missing_when_enabled(monkeypatch):
    monkeypatch.setenv("BOT_REQUIRE_INTERNAL_TOKEN", "1")
    monkeypatch.setenv("INTERNAL_TOKEN", "internal-token")
    common._INTERNAL_TOKEN_WARNING_EMITTED = False

    try:
        common.require_internal_token(None)
    except HTTPException as exc:
        assert exc.status_code == 401
    else:
        raise AssertionError("Expected HTTPException")


def test_require_internal_token_accepts_matching_value(monkeypatch):
    monkeypatch.setenv("BOT_REQUIRE_INTERNAL_TOKEN", "1")
    monkeypatch.setenv("INTERNAL_TOKEN", "internal-token")
    common._INTERNAL_TOKEN_WARNING_EMITTED = False

    assert common.require_internal_token("internal-token") is None
