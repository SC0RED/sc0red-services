"""Tests for shared web-search portfolio recovery (single + multi-pass)."""

from unittest.mock import MagicMock, patch

from signalfield_core.exceptions.base import EngineError

from src.pipeline.pipeline_steps.portfolio_websearch import (
    _DEEP_PASS_ANGLES,
    run_deep_web_search_discovery,
    run_web_search_discovery,
)

_GROUNDED = "src.pipeline.pipeline_steps.portfolio_websearch.run_grounded_ai_call"


def _grounded_return(companies):
    # run_grounded_ai_call → (label, content, elapsed, tokens, sources)
    return ("label", {"companies": companies}, 0.0, MagicMock(), [])


class TestRunWebSearchDiscovery:
    def test_returns_companies(self):
        with patch(
            _GROUNDED, return_value=_grounded_return([{"name": "A", "url": "https://a.com"}])
        ):
            out = run_web_search_discovery(MagicMock(), "https://firm.com")
        assert out == [{"name": "A", "url": "https://a.com"}]

    def test_seeds_prompt_with_known_names(self):
        with patch(_GROUNDED, return_value=_grounded_return([])) as mock_call:
            run_web_search_discovery(MagicMock(), "https://firm.com", ["Stripe", "Plaid"])
        prompt = mock_call.call_args.kwargs["user_prompt"]
        assert "Stripe, Plaid" in prompt

    def test_extra_instruction_appended(self):
        with patch(_GROUNDED, return_value=_grounded_return([])) as mock_call:
            run_web_search_discovery(
                MagicMock(), "https://firm.com", ["Stripe"], extra_instruction="Recent deals only."
            )
        assert "Recent deals only." in mock_call.call_args.kwargs["user_prompt"]

    def test_fail_soft_returns_empty(self):
        with patch(_GROUNDED, side_effect=EngineError("search down")):
            out = run_web_search_discovery(MagicMock(), "https://firm.com")
        assert out == []


class TestRunDeepWebSearchDiscovery:
    def test_multi_pass_unions_and_dedups(self):
        # Three passes (one per angle); pass 2 repeats a pass-1 hit (deduped).
        responses = [
            _grounded_return([{"name": "A", "url": "https://a.com"}]),
            _grounded_return(
                [{"name": "A", "url": "https://a.com"}, {"name": "B", "url": "https://b.com"}]
            ),
            _grounded_return([{"name": "C", "url": "https://c.com"}]),
        ]
        with patch(_GROUNDED, side_effect=responses) as mock_call:
            out = run_deep_web_search_discovery(MagicMock(), "https://firm.com", [])
        assert mock_call.call_count == len(_DEEP_PASS_ANGLES)
        assert {c["url"] for c in out} == {"https://a.com", "https://b.com", "https://c.com"}

    def test_excludes_nothing_when_seed_empty_but_dedups_within(self):
        responses = [
            _grounded_return([{"name": "A", "url": "https://a.com"}]),
            _grounded_return([{"name": "A", "url": "https://a.com"}]),
            _grounded_return([{"name": "A", "url": "https://a.com"}]),
        ]
        with patch(_GROUNDED, side_effect=responses):
            out = run_deep_web_search_discovery(MagicMock(), "https://firm.com", ["Seed Co"])
        assert len(out) == 1

    def test_later_passes_seeded_with_earlier_finds(self):
        responses = [
            _grounded_return([{"name": "A", "url": "https://a.com"}]),
            _grounded_return([]),
            _grounded_return([]),
        ]
        with patch(_GROUNDED, side_effect=responses) as mock_call:
            run_deep_web_search_discovery(MagicMock(), "https://firm.com", ["Seed Co"])
        # Pass 2's prompt should include both the seed and pass-1's find "A".
        second_prompt = mock_call.call_args_list[1].kwargs["user_prompt"]
        assert "Seed Co" in second_prompt
        assert "A" in second_prompt
