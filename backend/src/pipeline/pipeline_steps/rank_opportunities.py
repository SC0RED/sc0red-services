"""Pure Python opportunity ranking and deduplication — no AI calls, no IO.

Used by ParallelProfileRiskAndIdeation to select top ideations from 8
parallel ideation calls before passing them to the detail phase.
"""

from __future__ import annotations

IMPACT_RATING_SCORES: dict[str, int] = {"High": 3, "Medium": 2, "Low": 1}

_STOP_WORDS = frozenset(
    {"a", "an", "the", "and", "or", "of", "to", "in", "for", "with", "on", "at", "by", "is"}
)

_TITLE_OVERLAP_THRESHOLD = 0.6


def _normalise_words(title: str) -> set[str]:
    """Extract meaningful lowercase words from a title, excluding stop words."""
    return {word for word in title.lower().split() if word not in _STOP_WORDS}


def deduplicate_ideations(
    ideations: list[dict[str, object]],
    risk_scores: dict[str, float],
) -> list[dict[str, object]]:
    """Remove ideations with >60% word overlap in titles, keeping higher-scored category.

    Each ideation must have ``title`` and ``risk_category`` keys.
    ``risk_scores`` maps category id → score (used to break ties).
    """
    if not ideations:
        return []

    # Sort by parent risk score descending so the first seen wins
    sorted_ideations = sorted(
        ideations,
        key=lambda item: risk_scores.get(str(item["risk_category"]), 0.0),
        reverse=True,
    )

    kept: list[dict[str, object]] = []
    kept_word_sets: list[set[str]] = []

    for ideation in sorted_ideations:
        words = _normalise_words(str(ideation["title"]))
        if not words:
            kept.append(ideation)
            kept_word_sets.append(words)
            continue

        is_duplicate = False
        for existing_words in kept_word_sets:
            if not existing_words:
                continue
            overlap = len(words & existing_words)
            smaller = min(len(words), len(existing_words))
            if smaller > 0 and overlap / smaller > _TITLE_OVERLAP_THRESHOLD:
                is_duplicate = True
                break

        if not is_duplicate:
            kept.append(ideation)
            kept_word_sets.append(words)

    return kept


def rank_ideations(
    ideations: list[dict[str, object]],
    risk_scores: dict[str, float],
    max_count: int = 5,
) -> list[dict[str, object]]:
    """Rank ideations by impact_rating (High > Medium > Low), then by parent risk score.

    Returns up to ``max_count`` ideations.
    """
    return sorted(
        ideations,
        key=lambda item: (
            IMPACT_RATING_SCORES.get(str(item["impact_rating"]), 0),
            risk_scores.get(str(item["risk_category"]), 0.0),
        ),
        reverse=True,
    )[:max_count]


def derive_top_three_actions(ranked_ideations: list[dict[str, object]]) -> list[str]:
    """Derive top_three_immediate_actions from the top 3 ranked ideations."""
    return [str(ideation["title"]) for ideation in ranked_ideations[:3]]
