"""Cognito CustomMessage Lambda trigger — branded invitation emails.

Replaces Cognito's default plain-text invitation email with a branded
HTML email containing a direct link to the accept-invite page.
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


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
    frontend_domain = os.environ.get("FRONTEND_DOMAIN", "https://app.janus.ai")

    accept_url = f"{frontend_domain}/accept-invite?email={email}"

    event["response"]["emailSubject"] = "You've been invited to Janus"
    event["response"]["emailMessage"] = _INVITATION_HTML.format(
        email=email,
        temporary_password=temporary_password,
        accept_url=accept_url,
    )

    logger.info("Custom invitation email built for: %s", email)
    return event


_INVITATION_HTML = """\
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0; padding:0; background:#0d1117; font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#0d1117; padding:40px 20px;">
<tr><td align="center">
<table width="520" cellpadding="0" cellspacing="0" style="background:#161b22; border-radius:12px; border:1px solid #30363d;">

<!-- Header -->
<tr><td style="padding:32px 32px 24px; text-align:center; border-bottom:1px solid #30363d;">
<div style="font-size:24px; font-weight:700; color:#f0f6fc; letter-spacing:-0.5px;">
Janus
</div>
<div style="font-size:12px; color:#8b949e; margin-top:4px; text-transform:uppercase; letter-spacing:1px;">
AI Risk Intelligence
</div>
</td></tr>

<!-- Body -->
<tr><td style="padding:32px;">
<p style="color:#f0f6fc; font-size:16px; font-weight:600; margin:0 0 16px;">
You've been invited to Janus
</p>
<p style="color:#8b949e; font-size:14px; line-height:1.6; margin:0 0 24px;">
A member of your team has invited you to join their organisation on Janus,
the AI risk intelligence platform for private equity.
</p>

<!-- Credentials box -->
<div style="background:#0d1117; border:1px solid #30363d; border-radius:8px; padding:20px; margin:0 0 24px;">
<div style="color:#8b949e; font-size:12px; text-transform:uppercase; letter-spacing:0.5px; margin-bottom:12px;">
Your credentials
</div>
<table width="100%" cellpadding="0" cellspacing="0">
<tr>
<td style="color:#8b949e; font-size:13px; padding:4px 0;">Email</td>
<td style="color:#f0f6fc; font-size:13px; font-weight:500; padding:4px 0; text-align:right;">
{email}
</td>
</tr>
<tr>
<td style="color:#8b949e; font-size:13px; padding:4px 0;">Temporary password</td>
<td style="padding:4px 0; text-align:right;">
<code style="background:#1c2128; color:#58a6ff; padding:2px 8px; border-radius:4px; font-size:13px; font-family:monospace;">
{temporary_password}
</code>
</td>
</tr>
</table>
</div>

<!-- CTA Button -->
<div style="text-align:center; margin:0 0 24px;">
<a href="{accept_url}"
   style="display:inline-block; background:linear-gradient(135deg,#3b7bf6,#22d3ee); color:#fff; text-decoration:none; padding:12px 32px; border-radius:8px; font-size:14px; font-weight:600; letter-spacing:0.3px;">
Accept Invitation
</a>
</div>

<p style="color:#8b949e; font-size:13px; line-height:1.5; margin:0 0 8px;">
Click the button above to set your password and join the platform.
Your temporary password expires in 7 days.
</p>
<p style="color:#484f58; font-size:12px; margin:0;">
If you did not expect this invitation, you can safely ignore this email.
</p>
</td></tr>

<!-- Footer -->
<tr><td style="padding:20px 32px; border-top:1px solid #30363d; text-align:center;">
<p style="color:#484f58; font-size:11px; margin:0;">
Janus by SignalField &mdash; AI Risk Intelligence for Private Equity
</p>
</td></tr>

</table>
</td></tr>
</table>
</body>
</html>\
"""
