#!/usr/bin/env bash
# start_workers.sh — Inicia todos os workers RQ do pipeline Apogee.
#
# Uso:
#   bash scripts/start_workers.sh
#
# Variáveis de ambiente:
#   REDIS_URL  — URL do Redis (default: redis://localhost:6379)
#
# Cada worker roda em background. O script aguarda até que todos terminem
# (ou até Ctrl+C, que envia SIGINT para os processos filhos).

set -euo pipefail
cd "$(dirname "$0")/.."

echo "Iniciando workers Apogee..."
echo "  REDIS_URL=${REDIS_URL:-redis://localhost:6379}"
echo ""

uv run rq worker topic_miner  &
PID_MINER=$!
echo "  [topic_miner]  PID=$PID_MINER"

uv run rq worker researcher  &
PID_RESEARCHER=$!
echo "  [researcher]   PID=$PID_RESEARCHER"

uv run rq worker scriptwriter  &
PID_SCRIPT=$!
echo "  [scriptwriter] PID=$PID_SCRIPT"

uv run rq worker fact_checker  &
PID_FACT=$!
echo "  [fact_checker] PID=$PID_FACT"

echo ""
echo "Todos os workers iniciados. Pressione Ctrl+C para encerrar."

# Garante que Ctrl+C propague SIGINT para todos os filhos
trap 'kill $PID_MINER $PID_RESEARCHER $PID_SCRIPT $PID_FACT 2>/dev/null; exit 0' INT TERM

wait
