#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")"

echo "=== Setting up venv ==="
python3 -m venv .venv
source .venv/bin/activate
make install

echo ""
echo "=== Ruff check ==="
ruff check .

echo ""
echo "=== Ruff format ==="
ruff format --check .

echo ""
echo "=== Mypy ==="
cd servers/kiro-agents && mypy server.py && cd ../..
cd servers/kiro-checkpoint && mypy server.py && cd ../..
cd servers/mcp-proxy && mypy mcp_proxy.py && cd ../..

echo ""
echo "=== Tests (all servers including macOS-only) ==="
make test-mac

echo ""
echo "✅ All checks passed."
