#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

require_docker_engine
print_context_hint
SERVICE="${1:-dashboard-manager}"
print_info "Streaming logs for ${SERVICE}..."
docker_compose logs -f "$SERVICE"
