# Connect Kolibre staging to ChatGPT

Server-side protocol preparation is verified. **A connection inside an actual
ChatGPT account, its automatic refresh implementation, and model tool selection
have not been observed.** The shipped MCP Inspector was the real MCP client in
the public HTTPS tests. See [VPS_RESULTS.md](VPS_RESULTS.md) for exact evidence.

## Connection

1. Open [ChatGPT Plugins](https://chatgpt.com/plugins), select **+ → Add custom
   MCP server** (account/workspace policy must permit custom servers).
2. Name it `Kolibre staging`, with endpoint
   `https://books.drkhn.site/kolibre-mcp-stage/mcp` and OAuth authentication.
3. Choose a predefined/manual OAuth client and use client ID
   `kolibre-chatgpt-stage`. Read its client secret privately from
   `runtime/chatgpt-client.json` on this workstation, or root-only
   `/etc/kolibre-stage/chatgpt-client.json` on Oracle. Do not paste it into a
   chat, issue, or repository. This credential identifies the OAuth client;
   each reader must still sign in with their own Keycloak account.
4. The exact registered redirect is
   `https://chatgpt.com/connector_platform_oauth_redirect`. The provider
   advertises RFC 9207 issuer identification and its observed successful
   callbacks include the exact issuer. If ChatGPT's management page shows a
   different callback for your account, record that exact value for an
   administrator to register; do not use wildcard callbacks or open DCR.
5. Sign in as the synthetic Keycloak `founder` or `sister` identity and consent
   to `openid books:read` (ChatGPT may additionally request `offline_access`,
   which is enabled for these two synthetic readers). Their OIDC passwords differ from native Kolibre
   passwords; the workstation's private `runtime/staging-credentials.json`
   contains them. Both identities are already explicitly linked.
6. Review exactly four tools, create/install the plugin, then start a new chat
   with it selected. After future metadata changes, use **Refresh** and start
   a new conversation.

If the interface only offers automatic registration, record that limitation.
The DCR endpoint intentionally rejects OpenAI's unapproved source addresses.
Do not select anonymous authentication, use a common reader bearer, expose
unrestricted tools, or disable the registration policy to bypass this.

Suggested account-side acceptance prompts, in two separate ChatGPT accounts
or separately authenticated sessions (not two tabs sharing one linked login):

- “List my Kolibre libraries, then list books in the shared library.”
- “Search my private library for quasar. Show only my annotations.”
- Try the other synthetic reader's private identifier: no catalog, passages
  or notes may be returned, including for founder/admin.
- Revoke sister's shared-library grant through the administrative test harness;
  the next shared call must fail while her private calls still work. Restore
  the synthetic grant after the test.
- Wait past the normal five-minute OIDC token lifetime. Record whether ChatGPT
  refreshes automatically or requests reauthentication, then verify the same
  user's libraries/notes after reconnecting.

Record tool selection, arguments, success/denial and identity, without tokens
or passwords. Do not mark these account-side scenarios passed until observed.

## Why predefined registration

Current [official OpenAI authentication documentation](https://developers.openai.com/plugins/build/auth)
supports predefined OAuth clients as well as DCR/CIMD and requires S256 PKCE,
resource audience validation and discovery. A predefined confidential client
avoids broadening the existing source/URI restrictions on anonymous Keycloak
registration. It has an exact OpenAI callback, consent, only `books:read`, no
password/client-credentials/implicit grants, no web origins and required S256.
Client-secret POST exchange, real refresh rotation and replay rejection were
tested. Optional offline access is enabled only for this predefined client and
the two synthetic readers, with consent, a configured eight-hour maximum and
30-minute idle timeout; provider refresh_expires_in values are bounded. Both
basic and offline scope requests were verified after the final mapper fix.
The full eight-hour/30-minute wall-clock limits were not waited out. CIMD is not enabled or advertised; it would need a separately reviewed
Keycloak feature and trust configuration. No assertion that DCR from ChatGPT
works is made.

The [official connection guide](https://developers.openai.com/plugins/deploy/connect-chatgpt)
requires public HTTPS Streamable HTTP, discovery and tool metadata. The server
provides these at the URLs below. All four tool descriptors carry read-only,
non-destructive, idempotent, closed-world annotations and OAuth scope hints in
`_meta.securitySchemes`. Authentication is mandatory at the HTTP boundary,
independently of descriptive metadata; unauthenticated requests get an HTTP
401 with the protected-resource challenge. No anonymous fifth profile tool or
search/fetch compatibility shim was added. Deep-research-specific retrieval
contracts and enterprise verified-email restrictions are not demonstrated.

## Discovery and reproducible verification

- Resource: `https://books.drkhn.site/kolibre-mcp-stage/mcp`
- Protected-resource metadata:
  `https://books.drkhn.site/.well-known/oauth-protected-resource/kolibre-mcp-stage/mcp`
- Issuer: `https://books.drkhn.site/kolibre-auth-stage/realms/kolibre-stage`
- OAuth metadata:
  `https://books.drkhn.site/.well-known/oauth-authorization-server/kolibre-auth-stage/realms/kolibre-stage`

`deployment/configure_chatgpt.py` is an idempotent root-only provisioner. It
preserves an existing client secret and leaves DCR policies alone. For the
expiry probe, set **only this client's** TTL to 120 seconds, copy its private
configuration over SSH into a mode-0600 ignored runtime file, run
`deployment/chatgpt_probe.py`, and restore the client TTL to 300 seconds in a
shell trap. See [COMMANDS.md](COMMANDS.md). The probe intercepts the synthetic
browser's final redirect locally; it never delivers an authorization code to
OpenAI. It performs real PKCE/code/refresh HTTP exchanges, then actual
Inspector tool calls. This verifies the server contract, not ChatGPT itself.

Native authentication has no refresh-token endpoint. Native clients perform a
fresh password login after expiration; ChatGPT should use the OIDC flow.

The final Keycloak configuration uses separate audience mappers for the logical
resource client and exact MCP URL. A single mapper configured with both values
uses only the client audience; offline refresh exposed this error and correctly
received HTTP 401 until the configuration was fixed. Issuer/audience/scope
verification was never relaxed. See deployment/offline_probe.py and
verification/2026-11-07/ for the regression evidence.
