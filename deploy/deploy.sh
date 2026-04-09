#!/usr/bin/env sh
set -eu

DEPLOY_DIR="${1:-/opt/morningstar}"

cd "$DEPLOY_DIR"

docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d --remove-orphans
docker compose -f docker-compose.prod.yml ps
