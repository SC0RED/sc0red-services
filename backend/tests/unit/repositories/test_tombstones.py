"""Unit tests for the tombstone helper module.

The helpers are tiny but they are the single source of truth for the
soft-delete contract — exercising them in isolation pins the field
names + TTL window so an accidental rename or off-by-one in the
window calculation surfaces immediately rather than at runtime in
production.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta

from src.repositories.dynamodb._tombstones import (
    DELETED_AT_FIELD,
    TOMBSTONE_TTL_DAYS,
    TTL_FIELD,
    filter_live,
    is_live,
    tombstone_attributes,
)


class TestIsLive:
    def test_none_is_not_live(self):
        assert is_live(None) is False

    def test_record_without_deleted_at_is_live(self):
        assert is_live({"id": "x"}) is True

    def test_tombstoned_record_is_not_live(self):
        assert is_live({"id": "x", DELETED_AT_FIELD: "2026-04-27T00:00:00+00:00"}) is False

    def test_empty_dict_is_live(self):
        """An empty dict is non-None and has no `deleted_at` — treated as live.

        This case shouldn't happen in practice (callers either get a real
        item or None) but we still want is_live to be the strict inverse
        of is_tombstoned + a None check.
        """
        assert is_live({}) is True


class TestFilterLive:
    def test_empty_list(self):
        assert filter_live([]) == []

    def test_filters_tombstoned(self):
        items = [
            {"id": "live-1"},
            {"id": "doomed", DELETED_AT_FIELD: "2026-04-27T00:00:00+00:00"},
            {"id": "live-2", DELETED_AT_FIELD: ""},  # empty-string treated as live
        ]
        result = filter_live(items)
        assert [item["id"] for item in result] == ["live-1", "live-2"]


class TestTombstoneAttributes:
    def test_default_now_uses_current_time(self):
        before = int(time.time())
        attrs = tombstone_attributes()
        after = int(time.time())

        # `deleted_at` is an ISO 8601 string with timezone.
        deleted_at = attrs[DELETED_AT_FIELD]
        assert isinstance(deleted_at, str)
        # Round-trip parse to confirm it's valid ISO and in UTC.
        parsed = datetime.fromisoformat(deleted_at)
        assert parsed.tzinfo is not None

        # `ttl` is `now + TOMBSTONE_TTL_DAYS` epoch seconds, ± a couple
        # for clock drift between calls.
        ttl_seconds = attrs[TTL_FIELD]
        assert isinstance(ttl_seconds, int)
        expected_min = before + TOMBSTONE_TTL_DAYS * 86_400 - 5
        expected_max = after + TOMBSTONE_TTL_DAYS * 86_400 + 5
        assert expected_min <= ttl_seconds <= expected_max

    def test_explicit_now_is_deterministic(self):
        """Tests pass `now` to get reproducible timestamps."""
        when = datetime(2026, 4, 27, 12, 0, 0, tzinfo=UTC)
        attrs = tombstone_attributes(now=when)

        assert attrs[DELETED_AT_FIELD] == when.isoformat()
        # 90 days in seconds = 7776000.
        assert attrs[TTL_FIELD] == int((when + timedelta(days=TOMBSTONE_TTL_DAYS)).timestamp())

    def test_ttl_window_matches_constant(self):
        """If we ever change TOMBSTONE_TTL_DAYS, the test pins the maths."""
        when = datetime(2026, 1, 1, tzinfo=UTC)
        attrs = tombstone_attributes(now=when)
        delta_seconds = attrs[TTL_FIELD] - int(when.timestamp())
        assert delta_seconds == TOMBSTONE_TTL_DAYS * 86_400
