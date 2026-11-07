#!/usr/bin/env bash
# Userspace dependencies for tests/test_keycloak_local.py; never deploys them.
set -euo pipefail
cd "$(dirname "$0")/.."
test "$(uname -s)" = Linux && test "$(uname -m)" = x86_64 || {
  echo 'This pinned local-test bootstrap supports Linux x86_64 only.' >&2
  exit 1
}
dist="$PWD/runtime/keycloak-download"
mkdir -p "$dist"
download() {
  local name="$1" digest="$2" url="$3"
  if [ ! -f "$dist/$name" ]; then
    curl -fL --retry 2 "$url" -o "$dist/$name.partial"
    mv "$dist/$name.partial" "$dist/$name"
  fi
  echo "$digest  $dist/$name" | sha256sum -c -
}
download jdk.tar.gz d7f5d5cf865a2902b70ff549b97586a7d3f234e016f041ab447ea740c7d66d1c \
  'https://github.com/adoptium/temurin21-binaries/releases/download/jdk-21.0.13%2B9/OpenJDK21U-jdk_x64_linux_hotspot_21.0.13_9.tar.gz'
download keycloak.tar.gz dd124787283918bc597628887168333465ee2a811a389e0003569e52be7e487f \
  'https://github.com/keycloak/keycloak/releases/download/26.8.2/keycloak-26.8.2.tar.gz'
download caddy.tar.gz 727b91701a392de6ebc5027509f548bf39979e5216340d0faed8fa5e69c84f8b \
  'https://github.com/caddyserver/caddy/releases/download/v2.11.7/caddy_2.11.7_linux_amd64.tar.gz'
test -d "$dist/jdk-21.0.13+9" || tar -xzf "$dist/jdk.tar.gz" -C "$dist"
test -d "$dist/keycloak-26.8.2" || tar -xzf "$dist/keycloak.tar.gz" -C "$dist"
test -x "$dist/caddy" || tar -xzf "$dist/caddy.tar.gz" -C "$dist" caddy
