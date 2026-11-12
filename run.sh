#!/usr/bin/env bash
# CyberArena convenience runner — two independent products: the PLANT (simulation) and the AGENT (investigation).
#
#   ./run.sh setup        venv + install (copied install; reliable on Python 3.14) + both web UIs
#   ./run.sh plant        start PLANT backend  (plant :8000, dev/range :8100, modbus :5020)
#   ./run.sh agent        start AGENT backend  (:8200, pulls evidence from the plant over HTTP)
#   ./run.sh plant-ui     SAP-style plant console   http://localhost:5191
#   ./run.sh agent-ui     investigation console     http://localhost:5192
#   ./run.sh test         run the test suite
#   ./run.sh stop         stop every local service
#   ./run.sh docker       build + run all four containers (docker-compose.sites.yml)
# Re-run "./run.sh setup" after editing code under src/ (regular install, not editable).
set -euo pipefail
cd "$(dirname "$0")"
VENV=.venv
PY="$VENV/bin/python"
PLANT_URL="${PLANT_URL:-http://localhost:8000}"

kill_port() { local p=$1; local pid; pid=$(lsof -ti tcp:"$p" 2>/dev/null || true); [ -n "$pid" ] && kill -9 $pid 2>/dev/null || true; }

case "${1:-}" in
  setup)
    [ -d "$VENV" ] || python3 -m venv "$VENV"
    "$PY" -m pip install -q --upgrade pip
    "$PY" -m pip install -q ".[all]"
    ( cd web-plant && npm install --silent )
    ( cd web-agent && npm install --silent )
    echo "setup done. In four terminals: ./run.sh plant · ./run.sh agent · ./run.sh plant-ui · ./run.sh agent-ui"
    ;;
  plant)
    for p in 8000 8100 5020; do kill_port "$p"; done
    echo "PLANT  · plant http://localhost:8000 · range/dev http://localhost:8100 · modbus :5020"
    exec "$VENV/bin/cyberarena" range serve
    ;;
  agent)
    kill_port 8200
    # Load OPENAI_API_KEY (and anything else) from .env if present, so the GPT report works.
    [ -f .env ] && set -a && . ./.env && set +a
    echo "AGENT  · investigation http://localhost:8200 · target plant: $PLANT_URL · GPT report: $([ -n "${OPENAI_API_KEY:-}" ] && echo on || echo off)"
    ATTACK_TOKEN="${ATTACK_TOKEN:-arena-red-token}" PLANT_URL="$PLANT_URL" exec "$VENV/bin/cyberarena" agent serve
    ;;
  plant-ui) echo "Plant console  http://localhost:5191"; exec sh -c "cd web-plant && npm run dev" ;;
  agent-ui) echo "Agent console  http://localhost:5192"; exec sh -c "cd web-agent && npm run dev" ;;
  test) exec "$PY" -m pytest -q ;;
  docker) exec docker compose -f docker-compose.sites.yml up --build ;;
  stop) for p in 8000 8100 8200 5020 5191 5192; do kill_port "$p"; done; echo "stopped all local services" ;;
  *) echo "usage: ./run.sh [setup|plant|agent|plant-ui|agent-ui|test|stop|docker]"; exit 1 ;;
esac
