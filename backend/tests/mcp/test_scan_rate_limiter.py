"""Tests for the per-org MCP scan rate limiter."""

import os
from datetime import UTC, datetime
from unittest.mock import patch

import boto3
import pytest
from moto import mock_aws

from src.mcp.scan_rate_limiter import (
    DAILY_SCAN_LIMIT,
    HOURLY_SCAN_LIMIT,
    ScanRateLimitedError,
    ScanRateLimiter,
)


@pytest.fixture(autouse=True)
def _aws_credentials():
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"


@pytest.fixture
def limiter():
    with mock_aws():
        client = boto3.client("dynamodb", region_name="us-east-1")
        client.create_table(
            TableName="sc0red-services-test",
            KeySchema=[
                {"AttributeName": "pk", "KeyType": "HASH"},
                {"AttributeName": "sk", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "pk", "AttributeType": "S"},
                {"AttributeName": "sk", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        yield ScanRateLimiter("sc0red-services-test")


def _window_rows(limiter_instance, org_id):
    table = limiter_instance._table
    response = table.query(
        KeyConditionExpression=boto3.dynamodb.conditions.Key("pk").eq(f"RATE_LIMIT#{org_id}")
    )
    return {item["sk"]: item for item in response["Items"]}


class TestWithinLimits:
    def test_consumes_both_windows(self, limiter):
        limiter.check_and_increment("org-1")
        rows = _window_rows(limiter, "org-1")
        hour_rows = [sk for sk in rows if sk.startswith("SCAN#HOUR#")]
        day_rows = [sk for sk in rows if sk.startswith("SCAN#DAY#")]
        assert len(hour_rows) == 1
        assert len(day_rows) == 1
        assert rows[hour_rows[0]]["counter"] == 1
        assert rows[day_rows[0]]["counter"] == 1

    def test_rows_carry_ttl(self, limiter):
        limiter.check_and_increment("org-1")
        for item in _window_rows(limiter, "org-1").values():
            assert item["ttl"] > 0


class TestHourlyLimit:
    def test_trips_after_limit(self, limiter):
        for _ in range(HOURLY_SCAN_LIMIT):
            limiter.check_and_increment("org-1")
        with pytest.raises(ScanRateLimitedError, match=r"5 scans/hour.*Try again after"):
            limiter.check_and_increment("org-1")

    def test_limits_are_per_org(self, limiter):
        for _ in range(HOURLY_SCAN_LIMIT):
            limiter.check_and_increment("org-1")
        # org-2 is unaffected by org-1's exhaustion.
        limiter.check_and_increment("org-2")


class TestDailyLimit:
    def test_trips_after_limit_across_hours(self, limiter):
        # Spread calls across fake hour windows so only the DAY window fills.
        day = datetime(2026, 6, 11, tzinfo=UTC)
        calls = 0
        with patch("src.mcp.scan_rate_limiter.datetime") as mock_datetime:
            for hour in range(24):
                mock_datetime.now.return_value = day.replace(hour=hour)
                for _ in range(HOURLY_SCAN_LIMIT):
                    if calls == DAILY_SCAN_LIMIT:
                        break
                    limiter.check_and_increment("org-1")
                    calls += 1
            assert calls == DAILY_SCAN_LIMIT
            mock_datetime.now.return_value = day.replace(hour=23)
            with pytest.raises(ScanRateLimitedError, match=r"30 scans/day"):
                limiter.check_and_increment("org-1")

    def test_day_refusal_releases_the_hour_slot(self, limiter):
        # When the day window refuses, the already-consumed hour slot must be
        # handed back so rejected attempts don't eat the hourly budget.
        day = datetime(2026, 6, 11, tzinfo=UTC)
        with patch("src.mcp.scan_rate_limiter.datetime") as mock_datetime:
            calls = 0
            for hour in range(24):
                mock_datetime.now.return_value = day.replace(hour=hour)
                for _ in range(HOURLY_SCAN_LIMIT):
                    if calls == DAILY_SCAN_LIMIT:
                        break
                    limiter.check_and_increment("org-1")
                    calls += 1
            # Fresh hour window; day is exhausted.
            mock_datetime.now.return_value = day.replace(hour=23, minute=30)
            with pytest.raises(ScanRateLimitedError):
                limiter.check_and_increment("org-1")
        rows = _window_rows(limiter, "org-1")
        assert rows["SCAN#HOUR#2026-06-11T23"]["counter"] == 0


class TestWindowExpiry:
    def test_new_hour_window_starts_fresh(self, limiter):
        day = datetime(2026, 6, 11, tzinfo=UTC)
        with patch("src.mcp.scan_rate_limiter.datetime") as mock_datetime:
            mock_datetime.now.return_value = day.replace(hour=10)
            for _ in range(HOURLY_SCAN_LIMIT):
                limiter.check_and_increment("org-1")
            with pytest.raises(ScanRateLimitedError):
                limiter.check_and_increment("org-1")
            # Next hour: fresh counter.
            mock_datetime.now.return_value = day.replace(hour=11)
            limiter.check_and_increment("org-1")
