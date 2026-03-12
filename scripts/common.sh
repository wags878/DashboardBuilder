#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

print_info() {
  printf "[dashboard-builder] %s\n" "$*"
}

print_error() {
  printf "[dashboard-builder] ERROR: %s\n" "$*" >&2
}

ensure_compose_cmd() {
  if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    COMPOSE_MODE="docker"
    return
  fi

  if command -v docker-compose >/dev/null 2>&1; then
    COMPOSE_MODE="docker-compose"
    return
  fi

  print_error "Neither \"docker compose\" nor \"docker-compose\" is available."
  exit 1
}

docker_compose() {
  ensure_compose_cmd

  if [[ "${COMPOSE_MODE}" == "docker" ]]; then
    if [[ -n "${DOCKER_CONTEXT:-}" ]]; then
      docker --context "$DOCKER_CONTEXT" compose "$@"
    else
      docker compose "$@"
    fi
  else
    if [[ -n "${DOCKER_CONTEXT:-}" ]]; then
      DOCKER_CONTEXT="$DOCKER_CONTEXT" docker-compose "$@"
    else
      docker-compose "$@"
    fi
  fi
}

require_docker_engine() {
  if ! command -v docker >/dev/null 2>&1; then
    print_error "Docker CLI is not installed."
    exit 1
  fi

  if [[ -n "${DOCKER_CONTEXT:-}" ]]; then
    if ! docker --context "$DOCKER_CONTEXT" info >/dev/null 2>&1; then
      print_error "Docker engine is not reachable for context \"$DOCKER_CONTEXT\"."
      print_error "Start Docker Desktop or verify docker context configuration."
      exit 1
    fi
    return
  fi

  if ! docker info >/dev/null 2>&1; then
    print_error "Docker engine is not reachable. Start Docker Desktop or set DOCKER_CONTEXT."
    exit 1
  fi
}

ensure_env_file() {
  if [[ ! -f .env ]]; then
    if [[ -f .env.example ]]; then
      cp .env.example .env
      print_info "Created .env from .env.example"
    else
      print_error ".env and .env.example are both missing."
      exit 1
    fi
  fi
}

get_env_var() {
  local key="$1"
  local default_value="$2"
  local value=""

  if [[ -f .env ]]; then
    value="$(grep -E "^${key}=" .env | tail -n 1 | cut -d= -f2- || true)"
  fi

  if [[ -z "$value" ]]; then
    printf "%s" "$default_value"
  else
    printf "%s" "$value"
  fi
}

print_context_hint() {
  if [[ -n "${DOCKER_CONTEXT:-}" ]]; then
    print_info "Using docker context: ${DOCKER_CONTEXT}"
  fi
}
