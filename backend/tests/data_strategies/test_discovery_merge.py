"""Tests for portfolio discovery merge logic."""

from src.pipeline.pipeline_steps.portfolio_merge import (
    merge_results,
    normalize_url_key,
    sanitize_candidates,
)


class TestNormalizeUrlKeyWhitespace:
    def test_trailing_space_keys_same_as_clean(self):
        assert normalize_url_key("https://acme.com/ ") == normalize_url_key("https://acme.com/")

    def test_whitespace_variants_dedupe_in_merge(self):
        # The bug from dev: oseamalibu.com and "oseamalibu.com/ " (trailing space)
        # are the same company and must collapse to one.
        heuristic = [
            {"name": "OSEA", "url": "https://oseamalibu.com/"},
            {"name": "View Site", "url": "https://oseamalibu.com/ "},
        ]
        auto, needs = merge_results(heuristic, [])
        assert len(auto) + len(needs) == 1


class TestSanitizeCandidates:
    def test_generic_cta_name_derived_from_host(self):
        out = sanitize_candidates([{"name": "View Site", "url": "https://www.anthropic.com/"}])
        assert out[0]["name"] == "Anthropic"

    def test_cms_id_name_derived_from_slug(self):
        out = sanitize_candidates(
            [
                {
                    "name": "697777298512fb18e44dc499 Blue Pearl Module",
                    "url": "https://x.com/companies/bluepearl-veterinary-services",
                }
            ]
        )
        assert out[0]["name"] == "Bluepearl Veterinary Services"

    def test_login_rows_dropped(self):
        out = sanitize_candidates(
            [
                {"name": "Investor Login", "url": "https://dynamo.dynamosoftware.com/"},
                {"name": "Acme", "url": "https://acme.com"},
            ]
        )
        assert {c["name"] for c in out} == {"Acme"}

    def test_real_name_kept_and_url_stripped_and_source_preserved(self):
        out = sanitize_candidates(
            [{"name": "Wireless Logic", "url": "https://wirelesslogic.com/ ", "source": "site"}]
        )
        assert out[0]["name"] == "Wireless Logic"
        assert out[0]["url"] == "https://wirelesslogic.com/"
        assert out[0]["source"] == "site"

    def test_empty_name_derived_not_dropped_when_url_present(self):
        out = sanitize_candidates([{"name": "", "url": "https://stripe.com"}])
        assert out[0]["name"] == "Stripe"

    def test_nav_segment_url_falls_back_to_host(self):
        # A firm nav page ("/portfolio") is not a company name → use the host.
        out = sanitize_candidates([{"name": "View Site", "url": "https://kkr.com/portfolio"}])
        assert out[0]["name"] == "Kkr"

    def test_non_string_fields_do_not_crash(self):
        # Malformed extraction (None values) must be handled gracefully, not crash.
        out = sanitize_candidates(
            [
                {"name": None, "url": None},  # type: ignore[dict-item]
                {"name": "Acme", "url": "https://acme.com"},
            ]
        )
        assert {c["name"] for c in out} == {"Acme"}


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
