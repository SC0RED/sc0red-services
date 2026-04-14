"""OAuth token utilities — JWT signing, PKCE validation, code generation."""

from __future__ import annotations

import hashlib
import secrets
import time
from base64 import urlsafe_b64encode
from typing import Any

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


def generate_rsa_key_pair() -> tuple[str, str]:
    """Generate an RSA key pair for OAuth JWT signing.

    Returns:
        Tuple of (private_key_pem, public_key_pem) as strings.
    """
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    return private_pem, public_pem


def create_signed_access_token(
    *,
    private_key_pem: str,
    user_id: str,
    email: str,
    org_id: str,
    role: str,
    client_id: str,
    scopes: list[str],
    issuer: str,
    expires_in_seconds: int = 3600,
) -> str:
    """Sign a JWT access token for MCP OAuth.

    Args:
        private_key_pem: RSA private key in PEM format.
        user_id: The authenticated user's ID.
        email: The user's email.
        org_id: The user's organization ID.
        role: The user's role.
        client_id: The OAuth client that requested the token.
        scopes: Granted scopes.
        issuer: The issuer URL (MCP server URL).
        expires_in_seconds: Token lifetime in seconds (default 1 hour).

    Returns:
        Signed JWT string.
    """
    now = int(time.time())
    payload: dict[str, Any] = {
        "sub": user_id,
        "email": email,
        "org_id": org_id,
        "role": role,
        "client_id": client_id,
        "scope": " ".join(scopes),
        "iss": issuer,
        "iat": now,
        "exp": now + expires_in_seconds,
    }
    return jwt.encode(payload, private_key_pem, algorithm="RS256")


def verify_access_token(
    token: str,
    *,
    public_key_pem: str,
    issuer: str,
) -> dict[str, Any]:
    """Verify and decode a JWT access token.

    Args:
        token: The JWT to verify.
        public_key_pem: RSA public key in PEM format.
        issuer: Expected issuer URL.

    Returns:
        Decoded token payload.

    Raises:
        jwt.InvalidTokenError: If the token is invalid or expired.
    """
    return jwt.decode(
        token,
        public_key_pem,
        algorithms=["RS256"],
        issuer=issuer,
        options={"require": ["sub", "org_id", "exp", "iss"]},
    )


def generate_authorization_code() -> str:
    """Generate a cryptographically secure authorization code (160 bits entropy)."""
    return secrets.token_urlsafe(20)


def generate_refresh_token() -> str:
    """Generate a cryptographically secure refresh token."""
    return secrets.token_urlsafe(32)


def is_valid_pkce(code_verifier: str, code_challenge: str) -> bool:
    """Validate PKCE S256 challenge.

    Args:
        code_verifier: The original verifier string.
        code_challenge: The stored challenge to validate against.

    Returns:
        True if SHA256(code_verifier) matches code_challenge.
    """
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    computed_challenge = urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return computed_challenge == code_challenge


def hash_token(token: str) -> str:
    """Hash a token for storage (used as DynamoDB pk)."""
    return hashlib.sha256(token.encode()).hexdigest()
