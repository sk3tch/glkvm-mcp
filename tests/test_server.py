"""Tests for MCP server implementation."""

import json
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest

from glkvm_mcp.client import KVMClientError
from glkvm_mcp.ocr import OCRError
from glkvm_mcp.server import (
    PROTOCOL_VERSION,
    SERVER_NAME,
    SERVER_VERSION,
    MCPServer,
    make_error,
    make_response,
    read_message,
    write_message,
)
from glkvm_mcp.tools import TOOLS


class TestHelperFunctions:
    """Tests for helper functions."""

    def test_make_response(self):
        """make_response creates valid JSON-RPC response."""
        response = make_response(1, {"status": "ok"})
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 1
        assert response["result"] == {"status": "ok"}
        assert "error" not in response

    def test_make_response_with_string_id(self):
        """make_response works with string id."""
        response = make_response("abc-123", {"data": "test"})
        assert response["id"] == "abc-123"

    def test_make_error(self):
        """make_error creates valid JSON-RPC error."""
        response = make_error(1, -32600, "Invalid Request")
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 1
        assert response["error"]["code"] == -32600
        assert response["error"]["message"] == "Invalid Request"
        assert "data" not in response["error"]

    def test_make_error_with_data(self):
        """make_error includes optional data."""
        response = make_error(1, -32600, "Invalid", data={"detail": "missing field"})
        assert response["error"]["data"] == {"detail": "missing field"}

    def test_read_message_valid(self):
        """read_message parses valid JSON."""
        test_input = '{"jsonrpc": "2.0", "method": "test", "id": 1}\n'
        with patch("sys.stdin", StringIO(test_input)):
            message = read_message()
        assert message == {"jsonrpc": "2.0", "method": "test", "id": 1}

    def test_read_message_eof(self):
        """read_message returns None on EOF."""
        with patch("sys.stdin", StringIO("")):
            message = read_message()
        assert message is None

    def test_read_message_invalid_json(self):
        """read_message returns None for invalid JSON."""
        with patch("sys.stdin", StringIO("not json\n")), patch("sys.stderr", StringIO()):
            message = read_message()
        assert message is None

    def test_write_message(self):
        """write_message writes JSON to stdout."""
        output = StringIO()
        with patch("sys.stdout", output):
            write_message({"jsonrpc": "2.0", "id": 1, "result": "ok"})

        written = output.getvalue()
        assert written.endswith("\n")
        parsed = json.loads(written.strip())
        assert parsed["result"] == "ok"


class TestMCPServerInit:
    """Tests for MCPServer initialization."""

    def test_server_init(self, tmp_path, monkeypatch):
        """Server initializes with config and client."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("")
        monkeypatch.setenv("GLKVM_CONFIG", str(config_file))

        server = MCPServer()
        assert server.config is not None
        assert server.client is not None
        assert server.tool_handler is not None
        assert server.initialized is False


class TestHandleInitialize:
    """Tests for initialize handler."""

    def test_handle_initialize(self, tmp_path, monkeypatch):
        """initialize returns protocol version and capabilities."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("")
        monkeypatch.setenv("GLKVM_CONFIG", str(config_file))

        server = MCPServer()
        response = server.handle_initialize(1, {})

        assert response["id"] == 1
        result = response["result"]
        assert result["protocolVersion"] == PROTOCOL_VERSION
        assert "capabilities" in result
        assert "tools" in result["capabilities"]
        assert result["serverInfo"]["name"] == SERVER_NAME
        assert result["serverInfo"]["version"] == SERVER_VERSION

    def test_handle_initialize_sets_flag(self, tmp_path, monkeypatch):
        """initialize sets initialized flag."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("")
        monkeypatch.setenv("GLKVM_CONFIG", str(config_file))

        server = MCPServer()
        assert server.initialized is False
        server.handle_initialize(1, {})
        assert server.initialized is True


class TestHandleToolsList:
    """Tests for tools/list handler."""

    def test_handle_tools_list(self, tmp_path, monkeypatch):
        """tools/list returns all tools."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("")
        monkeypatch.setenv("GLKVM_CONFIG", str(config_file))

        server = MCPServer()
        response = server.handle_tools_list(1, {})

        assert response["id"] == 1
        assert "tools" in response["result"]
        assert len(response["result"]["tools"]) == len(TOOLS)


class TestHandleToolsCall:
    """Tests for tools/call handler."""

    @pytest.fixture
    def server(self, tmp_path, monkeypatch):
        """Create server with mocked tool handler."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("")
        monkeypatch.setenv("GLKVM_CONFIG", str(config_file))
        return MCPServer()

    def test_handle_tools_call_success(self, server):
        """Successful tool call returns result."""
        server.tool_handler.handle = MagicMock(return_value={"devices": []})

        response = server.handle_tools_call(
            1,
            {
                "name": "kvm_list_devices",
                "arguments": {},
            },
        )

        assert response["id"] == 1
        result = response["result"]
        assert "content" in result
        assert result["content"][0]["type"] == "text"
        # Result is JSON-encoded
        parsed = json.loads(result["content"][0]["text"])
        assert parsed == {"devices": []}

    def test_handle_tools_call_kvm_error(self, server):
        """KVMClientError returns error response."""
        server.tool_handler.handle = MagicMock(side_effect=KVMClientError("Connection failed"))

        response = server.handle_tools_call(
            1,
            {
                "name": "kvm_mouse_move",
                "arguments": {"device_id": "test", "x": 0, "y": 0},
            },
        )

        result = response["result"]
        assert result.get("isError") is True
        parsed = json.loads(result["content"][0]["text"])
        assert "error" in parsed
        assert "Connection failed" in parsed["error"]

    def test_handle_tools_call_ocr_error(self, server):
        """OCRError returns error response."""
        server.tool_handler.handle = MagicMock(side_effect=OCRError("ffmpeg not found"))

        response = server.handle_tools_call(
            1,
            {
                "name": "kvm_capture_screen",
                "arguments": {"device_id": "test"},
            },
        )

        result = response["result"]
        assert result.get("isError") is True
        parsed = json.loads(result["content"][0]["text"])
        assert "OCR error" in parsed["error"]

    def test_handle_tools_call_unexpected_error(self, server):
        """Unexpected exceptions return error response."""
        server.tool_handler.handle = MagicMock(side_effect=RuntimeError("Something broke"))

        response = server.handle_tools_call(
            1,
            {
                "name": "kvm_list_devices",
                "arguments": {},
            },
        )

        result = response["result"]
        assert result.get("isError") is True
        parsed = json.loads(result["content"][0]["text"])
        assert "Unexpected error" in parsed["error"]


class TestHandleMessage:
    """Tests for message routing."""

    @pytest.fixture
    def server(self, tmp_path, monkeypatch):
        """Create server."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("")
        monkeypatch.setenv("GLKVM_CONFIG", str(config_file))
        return MCPServer()

    def test_handle_message_initialize(self, server):
        """Routes initialize to handler."""
        response = server.handle_message(
            {
                "jsonrpc": "2.0",
                "method": "initialize",
                "id": 1,
                "params": {},
            }
        )
        assert response["result"]["protocolVersion"] == PROTOCOL_VERSION

    def test_handle_message_tools_list(self, server):
        """Routes tools/list to handler."""
        response = server.handle_message(
            {
                "jsonrpc": "2.0",
                "method": "tools/list",
                "id": 2,
                "params": {},
            }
        )
        assert "tools" in response["result"]

    def test_handle_message_tools_call(self, server):
        """Routes tools/call to handler."""
        server.tool_handler.handle = MagicMock(return_value={"success": True})
        response = server.handle_message(
            {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "id": 3,
                "params": {"name": "kvm_list_devices", "arguments": {}},
            }
        )
        assert "content" in response["result"]

    def test_handle_message_unknown_method(self, server):
        """Unknown method returns error."""
        response = server.handle_message(
            {
                "jsonrpc": "2.0",
                "method": "unknown/method",
                "id": 4,
                "params": {},
            }
        )
        assert "error" in response
        assert response["error"]["code"] == -32601
        assert "Method not found" in response["error"]["message"]

    def test_handle_message_notification(self, server):
        """Notifications (no id) return None."""
        response = server.handle_message(
            {
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
                "params": {},
            }
        )
        assert response is None

    def test_handle_message_initialized_notification(self, server):
        """notifications/initialized is handled."""
        response = server.handle_message(
            {
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
                "params": {},
            }
        )
        assert response is None  # Notifications don't return responses
