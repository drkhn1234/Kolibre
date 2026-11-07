# KOReader Flatpak sync check — 2026-11-07

**Core sync passed with the actual installed rocks.koreader.KOReader Flatpak.**
No application fix or redeployment was needed. Original normal KOReader profile
and books were not changed; it currently has no Kolibre plugin installed.

Actual binary/runtime: /app/lib/koreader in the installed Flatpak. Kolibre plugin
copied from current tested checkout into a separate KO_HOME:
`/home/drkhn/Projects/kolibre-integration/runtime/koreader-sync-profile`.
Dedicated founder-owned server device3 and synthetic shared book4, Flatpak sync
test, were created using the authenticated native APIs. Credentials remain only
in restricted ignored profile settings/device.json. Other reading state untouched.

## Passed

- Bundled Lua HTTP client authenticated its own device token over public HTTPS.
- Actual reader.lua booted, loaded the real Kolibre koplugin in FileManager.
- Plugin protocol-v2 sync downloaded the queued synthetic EPUB into the isolated
  book folder; server acknowledgement/history and local manifest persisted.
- KOReader document engine loaded the EPUB.
- Synthetic KOReader sidecar highlight/note and37% position uploaded through
  actual plugin dirty queues. Kolibre authenticated HTTP reads confirmed them.
- Sister's annotation response did not include the synthetic founder note.
- Changed this book's position to62% through the normal native web API; actual
  plugin _autoPullAllProgress wrote62% into KOReader DocSettings sidecar.

## Method and boundaries

This was a scripted integration check inside the real Flatpak, using SDL dummy
video and a priority2 KOReader user patch scheduling plugin operations after
startup. Test automation accepted ONLY the queued disposable download by
replacing its confirmation callback. Network, credentials, plugin sync logic,
filesystem and backend were real. Highlight/position inputs were synthetic
sidecar writes, not manually selected text or page turns in a visible window.
No auth decisions were mocked. No personal reading files were scanned.

Vocabulary/statistics database transfer, device backup/restore, deletion and
on-screen menu/touch interactions were NOT tested. This check does not certify
every plugin feature or physical e-reader hardware. No broad verification project
was started. No Oracle application/container restart was needed.

## Reproduce/recover

Profile settings are generated separately from private runtime credentials;
never copy them into Git. Template clients/koreader/2-pull-probe.lua is the final
pull-stage user patch; it expects the disposable book and earlier uploaded state.
After seeding a profile, actual command:

```
flatpak run --env=KO_HOME=/home/drkhn/Projects/kolibre-integration/runtime/koreader-sync-profile --env=SDL_VIDEODRIVER=dummy rocks.koreader.KOReader /home/drkhn/Projects/kolibre-integration/runtime/koreader-sync-profile/books
```

Do NOT run that probe against a personal KO_HOME. It sets synthetic test state.
The test profile's patches/2-kolibre-test.lua auto-runs and quits; remove/move
that disposable test patch before using the profile interactively. Normal
Flatpak launch still uses the original unchanged user profile. Enabling regular
sync there requires installing/configuring the Kolibre plugin for that profile;
the successful isolated test does not imply the normal profile was configured.

Raw evidence (ignored): evidence/deployment/koreader-plugin-sync-final.log,
koreader-plugin-pull.log, koreader-server-results.json; local result.txt and
settings/kolibre_manifest.lua. Startup-only standalone module attempts exited
before a reader context was initialized, so they were replaced with actual
reader.lua startup. The initial /devices/settings probe404 used a nonexistent
URL; actual /api/devices/me and plugin sync endpoints succeeded.
