"""MCP server implementation using stdio transport."""

import json
import sys
from typing import Any

from .client import KVMClient, KVMClientError
from .config import Config
from .ocr import OCRError
from .tools import TOOLS, ToolHandler

# MCP Protocol version
PROTOCOL_VERSION = "2024-11-05"

# Server info
SERVER_NAME = "glkvm-mcp"
SERVER_VERSION = "0.1.0"


def read_message() -> dict | None:
    """Read a JSON-RPC message from stdin."""
    line = sys.stdin.readline()
    if not line:
        return None
    try:
        return json.loads(line.strip())
    except json.JSONDecodeError as e:
        sys.stderr.write(f"Invalid JSON: {e}\n")
        return None


def write_message(message: dict) -> None:
    """Write a JSON-RPC message to stdout."""
    sys.stdout.write(json.dumps(message) + "\n")
    sys.stdout.flush()


def make_response(id: Any, result: Any) -> dict:
    """Create a JSON-RPC response."""
    return {
        "jsonrpc": "2.0",
        "id": id,
        "result": result,
    }


def make_error(id: Any, code: int, message: str, data: Any = None) -> dict:
    """Create a JSON-RPC error response."""
    error = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    return {
        "jsonrpc": "2.0",
        "id": id,
        "error": error,
    }


class MCPServer:
    """MCP server that handles JSON-RPC messages over stdio."""

    def __init__(self):
        self.config = Config()
        self.client = KVMClient(self.config)
        self.tool_handler = ToolHandler(self.config, self.client)
        self.initialized = False

    def handle_initialize(self, id: Any, params: dict) -> dict:
        """Handle initialize request."""
        self.initialized = True
        return make_response(
            id,
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {
                    "tools": {},
                },
                "serverInfo": {
                    "name": SERVER_NAME,
                    "version": SERVER_VERSION,
                },
            },
        )

    def handle_initialized(self, params: dict) -> None:
        """Handle initialized notification."""
        pass  # Nothing to do

    def handle_tools_list(self, id: Any, params: dict) -> dict:
        """Handle tools/list request."""
        return make_response(id, {"tools": TOOLS})

    def handle_tools_call(self, id: Any, params: dict) -> dict:
        """Handle tools/call request."""
        name = params.get("name")
        arguments = params.get("arguments", {})

        try:
            result = self.tool_handler.handle(name, arguments)
            return make_response(
                id,
                {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(result, indent=2),
                        }
                    ],
                },
            )
        except KVMClientError as e:
            return make_response(
                id,
                {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps({"error": str(e)}),
                        }
                    ],
                    "isError": True,
                },
            )
        except OCRError as e:
            return make_response(
                id,
                {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps({"error": f"OCR error: {e}"}),
                        }
                    ],
                    "isError": True,
                },
            )
        except Exception as e:
            return make_response(
                id,
                {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps({"error": f"Unexpected error: {e}"}),
                        }
                    ],
                    "isError": True,
                },
            )

    def handle_message(self, message: dict) -> dict | None:
        """Handle an incoming JSON-RPC message."""
        method = message.get("method")
        id = message.get("id")
        params = message.get("params", {})

        # Notifications (no id)
        if id is None:
            if method == "notifications/initialized":
                self.handle_initialized(params)
            return None

        # Requests (have id)
        if method == "initialize":
            return self.handle_initialize(id, params)
        elif method == "tools/list":
            return self.handle_tools_list(id, params)
        elif method == "tools/call":
            return self.handle_tools_call(id, params)
        else:
            return make_error(id, -32601, f"Method not found: {method}")

    def run(self) -> None:
        """Run the server, processing messages from stdin."""
        sys.stderr.write(f"{SERVER_NAME} v{SERVER_VERSION} starting...\n")

        while True:
            message = read_message()
            if message is None:
                break

            response = self.handle_message(message)
            if response is not None:
                write_message(response)


def main():
    """Entry point for the MCP server."""
    server = MCPServer()
    server.run()


if __name__ == "__main__":
    main()
