"""Optional, fail-closed OIDC access-token verification for delegated MCP clients.

All network endpoints and the expected issuer/audience are configured by the
server operator. A verified (issuer, subject) maps only to an explicitly linked
Kolibre user; no matching by username, email, display name or admin role.
"""
from __future__ import annotations

import os
import ssl
from urllib.parse import urlsplit

import httpx
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from .. import models


class OIDCIdentityError(Exception):
    """OIDC authentication or account mapping failed."""


def _settings() -> tuple[str, str, str]:
    issuer = (os.environ.get("KOLIBRE_OIDC_ISSUER") or "").strip().rstrip("/")
    audience = (os.environ.get("KOLIBRE_OIDC_AUDIENCE") or "").strip()
    jwks_uri = (os.environ.get("KOLIBRE_OIDC_JWKS_URI") or "").strip()
    if not all((issuer, audience, jwks_uri)):
        raise OIDCIdentityError("OIDC identity mapping disabled")
    for uri in (issuer, jwks_uri):
        parsed = urlsplit(uri)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise OIDCIdentityError("OIDC issuer and JWKS endpoint must use HTTPS")
        if parsed.fragment or parsed.query:
            raise OIDCIdentityError("OIDC URLs must not include query or fragment")
    return issuer, audience, jwks_uri


def verify_oidc_claims(token: str) -> tuple[str, str]:
    """Validate the issuer-signed token independently of Kolibre account state.

    Used during owner-initiated account linking only after verifying the
    owner's separate native Kolibre login and password.
    """
    issuer, audience, jwks_uri = _settings()
    try:
        header = jwt.get_unverified_header(token)
        if header.get("alg") != "RS256" or not isinstance(header.get("kid"), str):
            raise OIDCIdentityError("Unsupported access token signing algorithm")
        with httpx.Client(
            timeout=httpx.Timeout(4.0, connect=2.0),
            follow_redirects=False,
            trust_env=False,
            verify=ssl.create_default_context(cafile=os.environ.get("KOLIBRE_OIDC_CA_BUNDLE") or None),
        ) as client:
            response = client.get(jwks_uri)
            response.raise_for_status()
            if len(response.content) > 256_000:
                raise OIDCIdentityError("JWKS response too large")
            keys = response.json().get("keys", [])
        matches = [
            k for k in keys
            if isinstance(k, dict)
            and k.get("kid") == header["kid"]
            and k.get("kty") == "RSA"
            and k.get("use", "sig") == "sig"
            and k.get("alg", "RS256") == "RS256"
        ]
        if len(matches) != 1:
            raise OIDCIdentityError("Unknown OIDC signing key")
        claims = jwt.decode(
            token,
            matches[0],
            algorithms=["RS256"],
            issuer=issuer,
            audience=audience,
            options={"require_exp": True, "require_aud": True, "require_iss": True},
        )
        sub = claims.get("sub")
        if not isinstance(sub, str) or not sub or len(sub) > 512:
            raise OIDCIdentityError("Invalid OIDC subject")
        # Identity and audience alone do not grant delegated book access.
        # Enforce the application scope only after signature verification;
        # native Kolibre logins keep their existing authorization path.
        scope = claims.get("scope")
        if not isinstance(scope, str) or "books:read" not in scope.split():
            raise OIDCIdentityError("OIDC token requires books:read scope")
    except (JWTError, httpx.HTTPError, ValueError, TypeError, AttributeError, KeyError) as exc:
        raise OIDCIdentityError("OIDC verification failed") from exc

    return issuer, sub


def verify_oidc_user(token: str, db: Session) -> models.User:
    """Validate OIDC identity, then resolve a previously linked local account."""
    issuer, sub = verify_oidc_claims(token)
    user = db.query(models.User).filter(
        models.User.oidc_issuer == issuer,
        models.User.oidc_subject == sub,
    ).first()
    if user is None:
        raise OIDCIdentityError("OIDC subject is not linked to a Kolibre account")
    return user
