#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

require_docker_engine
ensure_env_file
print_context_hint
docker_compose ps

APP_PORT="$(get_env_var APP_PORT 8000)"
if command -v curl >/dev/null 2>&1; then
  print_info "Health check:"
  curl -fsS "http://localhost:${APP_PORT}/health" || true
  printf "\n"
fi
