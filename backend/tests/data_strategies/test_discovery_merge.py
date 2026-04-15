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
    """``_merge_results`` returns ``(auto_included, needs_validation)``.

    - ``auto_included``: companies found by BOTH paths (intersection, high confidence)
    - ``needs_validation``: companies found by only one path (remainder, need AI check)
    """

    def test_intersection_goes_to_auto_included(self):
        heuristic = [{"name": "Acme", "url": "https://acme.com"}]
        ai = [{"name": "Acme Corp", "url": "https://www.acme.com"}]
        auto_included, needs_validation = _merge_results(heuristic, ai)
        assert len(auto_included) == 1
        assert auto_included[0]["name"] == "Acme"  # heuristic version preferred
        assert needs_validation == []

    def test_disjoint_results_all_need_validation(self):
        heuristic = [{"name": "Acme", "url": "https://acme.com"}]
        ai = [{"name": "Beta", "url": "https://beta.com"}]
        auto_included, needs_validation = _merge_results(heuristic, ai)
        assert auto_included == []
        assert len(needs_validation) == 2

    def test_intersection_and_remainder_split(self):
        heuristic = [
            {"name": "Acme", "url": "https://acme.com"},
            {"name": "Gamma", "url": "https://gamma.com"},
        ]
        ai = [
            {"name": "Acme Corp", "url": "https://www.acme.com"},
            {"name": "Beta", "url": "https://beta.com"},
        ]
        auto_included, needs_validation = _merge_results(heuristic, ai)
        assert len(auto_included) == 1
        assert auto_included[0]["name"] == "Acme"
        remainder_names = {c["name"] for c in needs_validation}
        assert remainder_names == {"Gamma", "Beta"}

    def test_empty_heuristic(self):
        auto_included, needs_validation = _merge_results(
            [], [{"name": "Beta", "url": "https://beta.com"}]
        )
        assert auto_included == []
        assert len(needs_validation) == 1
        assert needs_validation[0]["name"] == "Beta"

    def test_empty_ai(self):
        auto_included, needs_validation = _merge_results(
            [{"name": "Acme", "url": "https://acme.com"}], []
        )
        assert auto_included == []
        assert len(needs_validation) == 1

    def test_both_empty(self):
        auto_included, needs_validation = _merge_results([], [])
        assert auto_included == []
        assert needs_validation == []

    def test_deduplicates_by_domain(self):
        heuristic = [
            {"name": "Acme", "url": "https://acme.com"},
            {"name": "Acme2", "url": "https://www.acme.com"},  # same domain
        ]
        ai: list[dict[str, str]] = []
        auto_included, needs_validation = _merge_results(heuristic, ai)
        # Same-domain heuristic entries dedupe; AI empty → all go to remainder
        assert auto_included == []
        assert len(needs_validation) == 1  # deduped
