# Actual ChatGPT acceptance — user-executed, 2026-11-07

Evidence source: screenshots and fresh tool results supplied by the user in this
Codex conversation. These are not automated server-side test transcripts.

Passed: founder enumeration/shared books/private search/private annotations;
exact four-tool discovery; direct founder → sister private book request denied
with `Library not found`; separate sister authentication; sister own books,
semantic-independent lexical search and own notes; direct sister → founder book,
full-text and annotation requests denied; unscoped annotations own-only.

User reports token-expiry handling succeeded. Automatic refresh versus prompted
reauthentication was not separately established.

Controlled live revocation: Codex removed only sister's shared grant via the
existing authenticated administrative API. Native verification shared=404,
private=200. User then supplied seven fresh ChatGPT tool calls: enumeration only
private; three explicit shared operations denied; private books/notes accessible;
unscoped notes private-only. After user reconnected as sister, shared remained
denied, private accessible. Codex restored the original edit/upload grant;
HTTP shared/private=200. User supplied three fresh ChatGPT calls confirming both
libraries, shared book, exactly two own annotations with no founder notes.

Private operation record: ignored runtime/vps-validation/chatgpt-revocation-completed.json.
No shared grant remains intentionally revoked. No claim of a full security audit.

## Recoverable baseline before knowledge retrieval

Git tags `staging-chatgpt-validated-20261107` anchor Kolibre 468af5dd6781a62fd344dce113366aee07c240c3
(application source c06a7cea001c853a9dfc74bd1e6e8ce627307e26) and CalibreMCP
072c06541585dc494ad137faf84603f8d6617194. Draft PRs remain unmerged.

Fresh encrypted backup: Oracle
/var/backups/kolibre-stage/snapshots/daily/20261107T162840Z.tar.gz.age.
Copied/decrypted to ignored local runtime/baseline-restore (restricted parent),
SQLite integrity_check=ok, 2 users, 3 EPUBs, nonempty idp.sql and root settings.
This is a successful decrypt/content recovery check, not a booted full-host or
PostgreSQL restore. Recovery identity stays workstation-only. Do not commit or
print the restored settings. Existing DEPLOYMENT.md backup procedure applies.
