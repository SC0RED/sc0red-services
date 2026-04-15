"""Tests for portfolio discovery merge logic."""

from src.pipeline.pipeline_steps.discover_portfolio import _merge_results, _normalize_domain


class TestNormalizeDomain:
    def test_strips_www(self):
        assert _normalize_domain("https://www.stripe.com") == "stripe.com"

    def test_no_www(self):
        assert _normalize_domain("https://stripe.com") == "stripe.com"

    def test_with_path(self):
        assert _normalize_domain("https://stripe.com/pricing") == "stripe.com"

    def test_adds_https(self):
        assert _normalize_domain("stripe.com") == "stripe.com"

    def test_lowercase(self):
        assert _normalize_domain("https://Stripe.COM") == "stripe.com"


class TestMergeResults:
    def test_intersection_included(self):
        heuristic = [{"name": "Acme", "url": "https://acme.com"}]
        ai = [{"name": "Acme Corp", "url": "https://www.acme.com"}]
        result = _merge_results(heuristic, ai)
        assert len(result) == 1
        assert result[0]["name"] == "Acme"  # heuristic version preferred

    def test_remainder_from_both_paths(self):
        heuristic = [{"name": "Acme", "url": "https://acme.com"}]
        ai = [{"name": "Beta", "url": "https://beta.com"}]
        result = _merge_results(heuristic, ai)
        assert len(result) == 2

    def test_intersection_first_then_remainder(self):
        heuristic = [
            {"name": "Acme", "url": "https://acme.com"},
            {"name": "Gamma", "url": "https://gamma.com"},
        ]
        ai = [
            {"name": "Acme Corp", "url": "https://www.acme.com"},
            {"name": "Beta", "url": "https://beta.com"},
        ]
        result = _merge_results(heuristic, ai)
        assert len(result) == 3
        # First should be intersection (acme.com)
        assert result[0]["name"] == "Acme"

    def test_empty_heuristic(self):
        result = _merge_results([], [{"name": "Beta", "url": "https://beta.com"}])
        assert len(result) == 1
        assert result[0]["name"] == "Beta"

    def test_empty_ai(self):
        result = _merge_results([{"name": "Acme", "url": "https://acme.com"}], [])
        assert len(result) == 1

    def test_both_empty(self):
        result = _merge_results([], [])
        assert len(result) == 0

    def test_deduplicates_by_domain(self):
        heuristic = [
            {"name": "Acme", "url": "https://acme.com"},
            {"name": "Acme2", "url": "https://www.acme.com"},  # same domain
        ]
        ai = []
        result = _merge_results(heuristic, ai)
        assert len(result) == 1  # deduped
