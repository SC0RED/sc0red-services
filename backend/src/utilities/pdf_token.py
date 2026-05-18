"""Short-lived signed token for the PDF render flow (Python implementation).

The async PDF export endpoint (``handle_post_export``) mints a token,
embeds it in the URL ``?t=...`` that the headless browser navigates to.
The ``/print/{analysisId}`` route validates the token before rendering.

Tokens are HMAC-SHA256 over a JSON payload ``{ analysisId, orgId, exp }``
with a 60-second TTL. The wire format is ``base64url(payload).base64url(sig)``,
matching the JWS-Compact shape but without the JOSE header overhead.

This module is the **Python port** of the canonical TypeScript
implementation at ``frontend/src/lib/pdf/token.ts`` (also duplicated
byte-identically at ``backend/lambdas/pdf-render/src/token.ts``). It
must produce byte-identical tokens to the TS implementation so the
Lambda's print-route navigation (verified server-side by the Next.js
print route, which uses ``verifyToken`` from the TS module) accepts
tokens we mint here.

Why three copies of the same algorithm: each runtime (Amplify SSR
Lambda, Node.js render Lambda, Python API Lambda) needs the crypto
inline so we don't take a network hop to a "token service." Drift is
prevented by:
- TypeScript canon + Lambda duplicate: ``npm run check-token-sync`` in CI
- This Python port: ``test_pdf_token_python_matches_typescript_vectors``
  validates the byte-output against frozen golden vectors.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time

TOKEN_TTL_SECONDS = 60


def _to_base64url(value: bytes) -> str:
    """Encode bytes as base64url (no padding) matching the TS implementation."""
    encoded = base64.b64encode(value).decode("ascii")
    return encoded.replace("=", "").replace("+", "-").replace("/", "_")


def sign_pdf_token(
    *,
    analysis_id: str,
    org_id: str,
    secret: str,
    now_seconds: int | None = None,
    ttl_seconds: int = TOKEN_TTL_SECONDS,
) -> str:
    """Sign a PDF render token for ``analysis_id`` scoped to ``org_id``.

    Returns ``base64url(payload).base64url(sig)``. The payload's JSON
    encoding is deliberately compact (no spaces) so the TS and Python
    implementations produce byte-identical outputs for the same inputs.

    Raises ``ValueError`` if ``secret`` is empty — a missing secret is
    a configuration bug, not a recoverable error.
    """
    if not secret:
        message = "sign_pdf_token: secret is required"
        raise ValueError(message)

    now = now_seconds if now_seconds is not None else int(time.time())
    payload = {"analysisId": analysis_id, "orgId": org_id, "exp": now + ttl_seconds}
    # ``separators=(",", ":")`` matches ``JSON.stringify``'s default
    # compact output — same byte sequence both runtimes sign over.
    payload_json = json.dumps(payload, separators=(",", ":"))
    encoded_payload = _to_base64url(payload_json.encode("utf-8"))
    signature = hmac.new(
        secret.encode("utf-8"),
        encoded_payload.encode("ascii"),
        hashlib.sha256,
    ).digest()
    return f"{encoded_payload}.{_to_base64url(signature)}"
