#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

require_docker_engine
ensure_env_file
print_context_hint
print_info "Building and starting dashboard-manager..."
docker_compose up --build -d
docker_compose ps

APP_PORT="$(get_env_var APP_PORT 8000)"
print_info "UI:      http://localhost:${APP_PORT}/"
print_info "API docs: http://localhost:${APP_PORT}/docs"
print_info "Health:   http://localhost:${APP_PORT}/health"
