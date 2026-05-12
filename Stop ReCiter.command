#!/bin/bash
# Stop ReCiter Desktop — double-click this from Finder.

set -u

cd "$(dirname "$0")"

say() { printf "\n\033[1;36m▸\033[0m %s\n" "$*"; }
err() { printf "\n\033[1;31m✗\033[0m %s\n" "$*" >&2; }

if ! command -v docker >/dev/null 2>&1; then
  err "Docker is not installed — nothing to stop."
  exit 0
fi

if ! docker info >/dev/null 2>&1; then
  err "Docker Desktop is not running — the containers are already down."
  exit 0
fi

say "Stopping ReCiter Desktop..."
docker compose down

say "Stopped. Data is preserved in Docker's volume — restart anytime."
echo ""
echo "This Terminal window can be closed."
