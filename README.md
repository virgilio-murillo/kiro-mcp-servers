# kiro-mcp-servers

Monorepo for custom [MCP (Model Context Protocol)](https://modelcontextprotocol.io/) servers.

## Servers

| Server | Description | Platform |
|--------|-------------|----------|
| **kiro-agents** | Orchestrates parallel investigations with live Ghostty dashboard | macOS only |
| **kiro-checkpoint** | Shadow git checkpointing for Kiro CLI sessions | Cross-platform |
| **mcp-proxy** | Transparent JSON-RPC proxy with hot-reload | Cross-platform |
| **chrome-tabs** | Tab picker GUI helper for mcp-chrome-tabs | macOS only |

## Requirements

- Python 3.10+
- `mcp[cli]>=1.0.0`

## Quick Start

```bash
# Install all servers (macOS)
make install

# Install cross-platform servers only (Linux)
make install-cross-platform

# Run tests
make test          # cross-platform tests (CI)
make test-mac      # all tests including macOS-only servers

# Lint
make lint
```

## Structure

```
servers/
├── kiro-agents/       # macOS-only — Ghostty + AppleScript integration
│   ├── server.py      # 7 MCP tools: investigation, correspondence, reports
│   ├── dashboard.sh   # Live TUI dashboard for investigations
│   └── pyproject.toml
├── kiro-checkpoint/   # Cross-platform — shadow git operations
│   ├── server.py      # 8 MCP tools: init, checkpoint, rollback, branch, diff
│   └── pyproject.toml
├── mcp-proxy/         # Cross-platform — stdlib only, zero deps
│   ├── mcp_proxy.py   # JSON-RPC proxy with reload_server tool injection
│   └── pyproject.toml
└── chrome-tabs/       # macOS-only — tkinter GUI helper
    └── tab_picker.py  # Tab selection dialog for mcp-chrome-tabs
```

## CI/CD

- **ci.yml**: Lint (ruff + mypy) + unit tests for cross-platform servers on ubuntu-latest
- **integration.yml**: EC2 Ubuntu + Arch Linux Docker integration tests (weekly + manual)
- **macOS**: Local only via `make test-mac`

## TODO

- [ ] Linux support for kiro-agents (mock Ghostty/AppleScript, use alternative terminal)
- [ ] Linux support for chrome-tabs tab picker (alternative to tkinter `-topmost`)
- [ ] Integration test suite
- [ ] Per-server README docs
