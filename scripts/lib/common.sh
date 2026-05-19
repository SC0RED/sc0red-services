#!/usr/bin/env bash
# Shared helpers for sc0red Services deploy scripts.

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m'

log() { echo -e "${YELLOW}▶ $*${NC}"; }
ok()  { echo -e "${GREEN}✓ $*${NC}"; }
err() { echo -e "${RED}✗ $*${NC}" >&2; exit 1; }

require_gh_token() {
    if [ -z "${GH_TOKEN:-}" ]; then
        if command -v gh >/dev/null 2>&1; then
            export GH_TOKEN
            GH_TOKEN=$(gh auth token)
            ok "GH_TOKEN obtained from gh CLI"
        else
            err "GH_TOKEN not set and gh CLI not available"
        fi
    fi
}
