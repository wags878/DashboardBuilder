#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

require_docker_engine
print_context_hint
print_info "Stopping dashboard-manager..."

if [[ "${1:-}" == "--volumes" ]]; then
  docker_compose down --volumes
else
  docker_compose down
fi
