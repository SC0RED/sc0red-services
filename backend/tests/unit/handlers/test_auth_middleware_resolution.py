"""Tests for `auth_middleware._resolve_user_id` — the actor-id translation chain.

These tests exercise the lookup-fallback logic introduced by
`fix-actor-attribution`: prefer `custom:legacy_user_id`, then
`find_by_cognito_sub`, then `find_by_email`. Each test calls the
private helper directly so we don't have to drag a real JWT through
the validation path.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from src.handlers.auth_middleware import _resolve_user_id


def _payload(**kwargs: str) -> dict[str, str]:
    """Convenience: build a JWT-shaped payload dict for the helper."""
    base = {"sub": "", "email": "", "custom:legacy_user_id": ""}
    base.update(kwargs)
    return base


def test_uses_legacy_user_id_when_present() -> None:
    """`custom:legacy_user_id` takes precedence over every fallback."""
    repo = MagicMock()
    payload = _payload(**{
        "custom:legacy_user_id": "u-1",
        "sub": "cognito-abc",
        "email": "alice@org.com",
    })
    assert _resolve_user_id(payload, repo) == "u-1"
    # Critically: no DynamoDB lookup happens when the JWT has the claim.
    repo.find_by_cognito_sub.assert_not_called()
    repo.find_by_email.assert_not_called()


def test_resolves_via_cognito_sub_when_legacy_id_missing() -> None:
    """`find_by_cognito_sub` is the primary fallback."""
    repo = MagicMock()
    repo.find_by_cognito_sub.return_value = {"id": "u-2", "email": "bob@org.com"}
    payload = _payload(sub="cognito-bob", email="bob@org.com")

    assert _resolve_user_id(payload, repo) == "u-2"

    repo.find_by_cognito_sub.assert_called_once_with("cognito-bob")
    # We shortcut once cognito_sub resolves — no email fallback fires.
    repo.find_by_email.assert_not_called()


def test_resolves_via_email_when_sub_lookup_fails() -> None:
    """Falls through to email when GSI5 returns None.

    Covers two scenarios:
    1. GSI5 still `CREATING` (sparse on day 0).
    2. Legacy user record has no `cognito_sub` written yet — backfill
       hasn't run.
    """
    repo = MagicMock()
    repo.find_by_cognito_sub.return_value = None
    repo.find_by_email.return_value = {"id": "u-3", "email": "carol@org.com"}
    payload = _payload(sub="cognito-carol", email="carol@org.com")

    assert _resolve_user_id(payload, repo) == "u-3"

    repo.find_by_cognito_sub.assert_called_once_with("cognito-carol")
    repo.find_by_email.assert_called_once_with("carol@org.com")


def test_returns_empty_when_all_three_paths_fail() -> None:
    """No legacy id, no sub match, no email match → empty string.

    The caller (`validate_token`) raises `ValueError` on empty —
    this preserves the "Token missing user identifier" behaviour.
    """
    repo = MagicMock()
    repo.find_by_cognito_sub.return_value = None
    repo.find_by_email.return_value = None
    payload = _payload(sub="cognito-ghost", email="ghost@org.com")

    assert _resolve_user_id(payload, repo) == ""

    repo.find_by_cognito_sub.assert_called_once_with("cognito-ghost")
    repo.find_by_email.assert_called_once_with("ghost@org.com")


def test_no_repo_falls_back_to_token_sub() -> None:
    """Legacy callers / tests that don't pass a repo get JWT-only behaviour.

    Matches the pre-`fix-actor-attribution` resolution exactly so we
    don't break any caller still using the older signature.
    """
    payload = _payload(sub="cognito-legacy", email="legacy@org.com")
    assert _resolve_user_id(payload, user_repo=None) == "cognito-legacy"


def test_no_repo_and_no_sub_returns_empty() -> None:
    """Defensive: if the JWT has nothing useful AND no repo is passed,
    return empty so the caller raises 401 cleanly.
    """
    payload = _payload(email="orphan@org.com")
    assert _resolve_user_id(payload, user_repo=None) == ""


def test_skip_email_lookup_when_no_email_in_token() -> None:
    """A token with `sub` but no `email` only tries the cognito_sub path.

    Common shape for service-style tokens — no point asking the repo
    `find_by_email("")` and getting a misleading None back.
    """
    repo = MagicMock()
    repo.find_by_cognito_sub.return_value = None
    payload = _payload(sub="cognito-svc")

    assert _resolve_user_id(payload, repo) == ""

    repo.find_by_cognito_sub.assert_called_once_with("cognito-svc")
    repo.find_by_email.assert_not_called()


def test_user_record_without_id_is_treated_as_no_match() -> None:
    """Defensive: a repo lookup that returns a user dict missing `id`
    falls through to the next path rather than crashing.
    """
    repo = MagicMock()
    repo.find_by_cognito_sub.return_value = {"email": "headless@org.com"}  # no `id`
    repo.find_by_email.return_value = {"id": "u-rescued"}
    payload = _payload(sub="cognito-headless", email="headless@org.com")

    assert _resolve_user_id(payload, repo) == "u-rescued"
