#!/usr/bin/env bash
set -euo pipefail

export PORT="${PORT:-7860}"
export VERITAS_PUBLIC_DEMO="${VERITAS_PUBLIC_DEMO:-1}"
export VERITAS_DEMO_MODE="${VERITAS_DEMO_MODE:-1}"
export VERITAS_MEMORY_DIR="${VERITAS_MEMORY_DIR:-/tmp/veritas_memory}"
export VERITAS_KNOWLEDGE_DIR="${VERITAS_KNOWLEDGE_DIR:-/tmp/veritas_knowledge}"
export VERITAS_VAULT_DIR="${VERITAS_VAULT_DIR:-/tmp/veritas_vault}"
export VERITAS_UPLOAD_DIR="${VERITAS_UPLOAD_DIR:-/tmp/veritas_uploads}"
export VERITAS_RUNTIME_DIR="${VERITAS_RUNTIME_DIR:-/tmp/veritas_runtime}"

mkdir -p "$VERITAS_MEMORY_DIR" "$VERITAS_KNOWLEDGE_DIR" "$VERITAS_VAULT_DIR" "$VERITAS_UPLOAD_DIR" "$VERITAS_RUNTIME_DIR"

# Seed only the fictional Harbor Point demo matter. Do not copy private Azure
# data, legal evidence, runtime memory, logs, databases, or credentials.
/app/.venv/bin/python demo_seed.py || true

exec /app/.venv/bin/python -m uvicorn app:app --host 0.0.0.0 --port "$PORT"
