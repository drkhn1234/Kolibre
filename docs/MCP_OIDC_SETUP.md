# Optional OIDC identity binding for the restricted MCP bridge

**Draft integration, disabled by default.** Do not enable on production until
the upstream IdP configuration and end-to-end browser OAuth flow are tested.

## Trust boundary

Kolibre's existing local password/JWT login stays enabled. An external OIDC
provider may issue a **signed RS256 JWT access token**, which Kolibre verifies
against a server-configured JWKS URL using fixed issuer and audience.

A validated external subject is admitted **only** if its exact
`(issuer, subject)` pair is already linked to an existing Kolibre user. No
automatic creation, username/email matching, founder override, or admin-managed
linking to another person's account is allowed.

An already-authorized Kolibre user can link their OWN identity only by proving
both their existing native Kolibre password and possession of a valid signed
OIDC access token. The current implementation provides the backend endpoint
but not an interactive browser account-linking UI.

## Kolibre environment configuration

```env
KOLIBRE_OIDC_ISSUER=https://login.example.test/realms/books
KOLIBRE_OIDC_AUDIENCE=kolibre-mcp
KOLIBRE_OIDC_JWKS_URI=https://login.example.test/realms/books/protocol/openid-connect/certs
```

These are **illustrative values**. Configure a real OIDC provider that issues
JWT-formatted **access** tokens for the designated audience. Opaque access
tokens, ID tokens used in place of access tokens, HS256 tokens, expired tokens,
or tokens from any other issuer are not accepted.

All three variables must be set to enable external tokens. HTTPS is required.
Kolibre uses outbound TLS without following redirects and without inherited
proxy environment variables to fetch signing keys.

An absent or invalid configuration fails closed for external tokens, not for
local Kolibre JWT login. A separate idempotent database migration adds nullable
`users.oidc_issuer` and `users.oidc_subject` with a unique composite index.
Existing local users are never linked automatically.

## Owner-controlled linking

`POST /api/users/me/oidc-link`

- Must authenticate with the user's original Kolibre JWT, not an OIDC token.
- JSON: `{"password":"<Kolibre account password>","oidc_access_token":"<OIDC JWT>"}`
- The submitted OIDC JWT must be valid *now* for the configured issuer/audience.
- Only the authenticated user's own row is updated. Linking another person's
  already-mapped subject returns 409. Changing a linked identity requires
  unlinking first.

`GET /api/users/me/oidc-status` reports whether the caller has a link.
`POST /api/users/me/oidc-unlink` accepts
`{"password":"<Kolibre account password>"}`.

Both also require a **native** Kolibre JWT. Do not log or persist either
password or OIDC bearer token. Only the verified issuer and subject are stored.

For actual users, replace manual token entry with a consent-aware web flow
before production deployment. Use only synthetic accounts on staging now.

## Important unresolved items

- The chosen IdP's OAuth client registration and authorization code flow
  (including PKCE and refresh) must work with actual MCP clients.
- Revocation of an already-issued access token may not be immediate: it
  remains cryptographically valid until expiry unless the IdP supplies an
  introspection/revocation mechanism. Set short token lifetimes.
- JWKS refresh currently happens on each external token check. Add a bounded
  key cache and rotation tests before high-volume use.
- Kolibre's broader multi-user security and CalibreMCP's private RAG work
  are separate draft milestones.
- E2EE/root-operator privacy is deferred; this is application-level only.

Reference integration: CalibreMCP's
`feature/kolibre-authenticated-mcp-bridge` branch.
