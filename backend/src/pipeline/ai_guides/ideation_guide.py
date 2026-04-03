"""Ideation quality guide — injected into opportunity ideation system prompts.

Provides specificity standards, observable-evidence grounding, anti-pattern corrections,
and strategic category calibration to produce more actionable, company-specific ideas.
"""

from src.pipeline.prompts.loader import load_guide

IDEATION_GUIDE = load_guide("ideation_guide")
