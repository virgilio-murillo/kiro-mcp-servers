.PHONY: install test test-integration test-mac lint clean

install:
	pip install -e servers/kiro-agents
	pip install -e servers/kiro-checkpoint
	pip install -e servers/mcp-proxy
	pip install ruff mypy pytest pytest-asyncio

install-cross-platform:
	pip install -e servers/kiro-checkpoint
	pip install -e servers/mcp-proxy
	pip install ruff mypy pytest pytest-asyncio

test:
	pytest servers/kiro-checkpoint/tests servers/mcp-proxy/tests -v

test-mac:
	pytest servers/kiro-agents/tests servers/kiro-checkpoint/tests servers/mcp-proxy/tests -v

test-integration:
	pytest tests/integration/ -v --timeout=60

lint:
	ruff check .
	ruff format --check .
	cd servers/kiro-agents && mypy server.py
	cd servers/kiro-checkpoint && mypy server.py
	cd servers/mcp-proxy && mypy mcp_proxy.py

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name '*.egg-info' -exec rm -rf {} +
	rm -rf .mypy_cache .ruff_cache .pytest_cache
