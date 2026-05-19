"""Cognito CustomMessage Lambda trigger — branded invitation emails.

Replaces Cognito's default plain-text invitation email with a branded
HTML email containing a direct link to the accept-invite page.

The HTML template is loaded from templates/invitation_email.html —
not inline in Python (per CLAUDE.md mandatory patterns).
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_TEMPLATES_DIR = Path(__file__).parent / "templates"
_INVITATION_HTML = (_TEMPLATES_DIR / "invitation_email.html").read_text()


def handle_custom_message(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    """Lambda handler for Cognito CustomMessage trigger.

    Only customizes AdminCreateUser (invitation) emails. All other
    message types (verification, forgot-password) use Cognito defaults.
    """
    trigger_source = event.get("triggerSource", "")

    if trigger_source == "CustomMessage_AdminCreateUser":
        return _build_invitation_email(event)

    # All other triggers: return unchanged (use Cognito defaults)
    return event


def _build_invitation_email(event: dict[str, Any]) -> dict[str, Any]:
    """Build branded HTML invitation email."""
    email = event["request"]["usernameParameter"]
    temporary_password = event["request"]["codeParameter"]
    frontend_domain = os.environ.get("FRONTEND_DOMAIN", "")
    if not frontend_domain:
        logger.warning("FRONTEND_DOMAIN not set — using placeholder in invitation link")
        frontend_domain = "https://app.example.com"

    accept_url = f"{frontend_domain}/accept-invite?email={email}"

    event["response"]["emailSubject"] = "You've been invited to sc0red Advisory"
    event["response"]["emailMessage"] = _INVITATION_HTML.format(
        email=email,
        temporary_password=temporary_password,
        accept_url=accept_url,
    )

    logger.info("Custom invitation email built for: %s", email)
    return event
