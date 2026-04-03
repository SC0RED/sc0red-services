"""Risk scoring calibration guide — injected into risk assessment system prompts.

Provides score range definitions, category-specific anchors, anti-pattern corrections,
and observable proxy patterns to eliminate score variance across runs.
"""

from src.pipeline.prompts.loader import load_guide

RISK_SCORING_GUIDE = load_guide("risk_scoring_guide")
