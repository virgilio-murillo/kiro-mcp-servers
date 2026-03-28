"""Tests for mcp-proxy."""
import json


def test_module_imports():
    from mcp_proxy import MCPProxy, main, RELOAD_TOOL
    assert RELOAD_TOOL["name"] == "reload_server"


def test_reload_tool_schema():
    from mcp_proxy import RELOAD_TOOL
    assert RELOAD_TOOL["inputSchema"]["type"] == "object"
    assert RELOAD_TOOL["inputSchema"]["required"] == []
