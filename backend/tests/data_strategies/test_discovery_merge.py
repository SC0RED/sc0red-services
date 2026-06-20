"""Tests for portfolio discovery merge logic."""

from src.pipeline.pipeline_steps.portfolio_merge import merge_results, normalize_url_key


class TestNormalizeUrlKey:
    def test_strips_www(self):
        assert normalize_url_key("https://www.stripe.com") == "stripe.com"

    def test_no_www(self):
        assert normalize_url_key("https://stripe.com") == "stripe.com"

    def test_root_and_trailing_slash_equal(self):
        assert normalize_url_key("https://stripe.com/") == normalize_url_key("https://stripe.com")

    def test_path_is_part_of_key(self):
        # Path-aware: distinct paths on the same host are distinct keys.
        assert normalize_url_key("https://firm.com/portfolio/a") == "firm.com/portfolio/a"
        assert normalize_url_key("https://firm.com/portfolio/a") != normalize_url_key(
            "https://firm.com/portfolio/b"
        )

    def test_adds_https(self):
        assert normalize_url_key("stripe.com") == "stripe.com"

    def test_lowercase_host(self):
        assert normalize_url_key("https://Stripe.COM") == "stripe.com"

    def test_lowercase_path(self):
        key = normalize_url_key("https://firm.com/Portfolio/Stripe")
        assert key == "firm.com/portfolio/stripe"


class TestMergeResults:
    """``merge_results`` returns ``(auto_included, needs_validation)``.

    - ``auto_included``: companies found by BOTH paths (intersection, high confidence)
    - ``needs_validation``: companies found by only one path (remainder, need AI check)
    """

    def test_intersection_goes_to_auto_included(self):
        heuristic = [{"name": "Acme", "url": "https://acme.com"}]
        ai = [{"name": "Acme Corp", "url": "https://www.acme.com"}]
        auto_included, needs_validation = merge_results(heuristic, ai)
        assert len(auto_included) == 1
        assert auto_included[0]["name"] == "Acme"  # heuristic version preferred
        assert needs_validation == []

    def test_disjoint_results_all_need_validation(self):
        heuristic = [{"name": "Acme", "url": "https://acme.com"}]
        ai = [{"name": "Beta", "url": "https://beta.com"}]
        auto_included, needs_validation = merge_results(heuristic, ai)
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
        auto_included, needs_validation = merge_results(heuristic, ai)
        assert len(auto_included) == 1
        assert auto_included[0]["name"] == "Acme"
        remainder_names = {c["name"] for c in needs_validation}
        assert remainder_names == {"Gamma", "Beta"}

    def test_empty_heuristic(self):
        auto_included, needs_validation = merge_results(
            [], [{"name": "Beta", "url": "https://beta.com"}]
        )
        assert auto_included == []
        assert len(needs_validation) == 1
        assert needs_validation[0]["name"] == "Beta"

    def test_empty_ai(self):
        auto_included, needs_validation = merge_results(
            [{"name": "Acme", "url": "https://acme.com"}], []
        )
        assert auto_included == []
        assert len(needs_validation) == 1

    def test_both_empty(self):
        auto_included, needs_validation = merge_results([], [])
        assert auto_included == []
        assert needs_validation == []

    def test_deduplicates_same_url_www_variant(self):
        heuristic = [
            {"name": "Acme", "url": "https://acme.com"},
            {"name": "Acme2", "url": "https://www.acme.com"},  # same host, root path
        ]
        ai: list[dict[str, str]] = []
        auto_included, needs_validation = merge_results(heuristic, ai)
        # www/root variants of the same URL still dedupe; AI empty → remainder
        assert auto_included == []
        assert len(needs_validation) == 1  # deduped

    def test_same_domain_distinct_detail_pages_not_collapsed(self):
        # Regression: a firm's per-company detail pages share a domain but are
        # distinct companies — they must NOT collapse to one.
        heuristic = [
            {"name": f"Co{i}", "url": f"https://firm.com/portfolio/co{i}"} for i in range(25)
        ]
        auto_included, needs_validation = merge_results(heuristic, [])
        assert auto_included == []
        assert len(needs_validation) == 25  # all preserved, not collapsed to 1
