"""Lambda entry points for Step Function state handlers.

Each handler is a separate Lambda function in CDK, sharing the same
codebase. They're lightweight — ~2s for send_wave, ~100ms for check/mark.
"""

from __future__ import annotations

import logging
import sys
from typing import Any

from src.handlers.step_function_handlers import (
    handle_check_wave,
    handle_mark_complete,
    handle_send_wave,
)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, stream=sys.stdout)


def handle_send_wave_event(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Lambda entry: dispatch a wave of company analyses."""
    return handle_send_wave(event, context)


def handle_check_wave_event(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Lambda entry: check if the current wave is complete."""
    return handle_check_wave(event, context)


def handle_mark_complete_event(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Lambda entry: mark the scan as complete."""
    return handle_mark_complete(event, context)
