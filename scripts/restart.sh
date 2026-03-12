#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

require_docker_engine
ensure_env_file
print_context_hint
print_info "Restarting dashboard-manager..."
docker_compose down
docker_compose up --build -d
docker_compose ps
