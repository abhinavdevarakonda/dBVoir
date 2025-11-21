#!/bin/bash
# Jellyfin library refresh script
# Loads configuration from .env file

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="$PROJECT_ROOT/.env"

# Load .env file
if [ -f "$ENV_FILE" ]; then
    set -a  # automatically export all variables
    source <(grep -v '^#' "$ENV_FILE" | grep -v '^$' | sed 's/^/export /')
    set +a
fi

# Set defaults
JELLYFIN_URL="${JELLYFIN_URL:-http://10.0.0.8:8096}"
JELLYFIN_API_KEY="${JELLYFIN_API_KEY:-}"
JELLYFIN_LIBRARY_ID="${JELLYFIN_LIBRARY_ID:-}"

if [ -z "$JELLYFIN_API_KEY" ]; then
    echo "Error: JELLYFIN_API_KEY not set" >&2
    echo "Set it in .env file or environment variable" >&2
    exit 1
fi

# Build URL
URL="${JELLYFIN_URL}/Library/Refresh?Recursive=true&MetadataRefreshMode=Default"
[ -n "$JELLYFIN_LIBRARY_ID" ] && URL="${URL}&ItemIds=${JELLYFIN_LIBRARY_ID}"

# Trigger refresh
if curl -s -f -X POST "$URL" \
    -H "X-Emby-Token: ${JELLYFIN_API_KEY}" \
    -H "Content-Type: application/json" > /dev/null; then
    echo "Jellyfin library refresh triggered successfully"
else
    echo "Error triggering Jellyfin refresh" >&2
    exit 1
fi