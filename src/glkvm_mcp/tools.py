"""MCP tool definitions and handlers."""

import base64
from typing import Any

from .client import KVMClient
from .config import Config
from .ocr import (
    find_text,
    ocr_screenshot,
    pixel_to_hid,
    process_screenshot,
)

# Tool definitions for MCP
TOOLS = [
    {
        "name": "kvm_list_devices",
        "description": "List all configured KVM devices",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "kvm_add_device",
        "description": "Add a new KVM device to the configuration",
        "inputSchema": {
            "type": "object",
            "properties": {
                "device_id": {
                    "type": "string",
                    "description": "Unique identifier for the device (e.g., 'kvm-office')",
                },
                "ip": {
                    "type": "string",
                    "description": "IP address of the KVM device",
                },
                "port": {
                    "type": "integer",
                    "description": "Port number (default: 8443)",
                },
                "name": {
                    "type": "string",
                    "description": "Friendly name for the device",
                },
            },
            "required": ["device_id", "ip"],
        },
    },
    {
        "name": "kvm_remove_device",
        "description": "Remove a KVM device from the configuration",
        "inputSchema": {
            "type": "object",
            "properties": {
                "device_id": {
                    "type": "string",
                    "description": "ID of the device to remove",
                },
            },
            "required": ["device_id"],
        },
    },
    {
        "name": "kvm_capture_screen",
        "description": "Capture a screenshot from a KVM device. Returns base64-encoded JPEG image.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "device_id": {
                    "type": "string",
                    "description": "ID of the KVM device",
                },
                "max_width": {
                    "type": "integer",
                    "description": "Maximum width for output image (default: 1280)",
                },
                "max_height": {
                    "type": "integer",
                    "description": "Maximum height for output image (default: 720)",
                },
                "quality": {
                    "type": "integer",
                    "description": "JPEG quality 1-100 (default: 70)",
                },
            },
            "required": ["device_id"],
        },
    },
    {
        "name": "kvm_screenshot_with_ocr",
        "description": "Capture a screenshot and extract text using OCR. Returns the image, extracted text, and bounding boxes for each word.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "device_id": {
                    "type": "string",
                    "description": "ID of the KVM device",
                },
                "max_width": {
                    "type": "integer",
                    "description": "Maximum width for output image (default: 1280)",
                },
                "max_height": {
                    "type": "integer",
                    "description": "Maximum height for output image (default: 720)",
                },
                "quality": {
                    "type": "integer",
                    "description": "JPEG quality 1-100 (default: 70)",
                },
            },
            "required": ["device_id"],
        },
    },
    {
        "name": "kvm_find_and_click",
        "description": "Find text on screen using OCR and optionally click it. If multiple matches found, returns all coordinates without clicking.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "device_id": {
                    "type": "string",
                    "description": "ID of the KVM device",
                },
                "text": {
                    "type": "string",
                    "description": "Text to find on screen (case-insensitive, partial match)",
                },
                "click": {
                    "type": "boolean",
                    "description": "Whether to click if single match found (default: true)",
                },
            },
            "required": ["device_id", "text"],
        },
    },
    {
        "name": "kvm_mouse_move",
        "description": "Move the mouse cursor to absolute coordinates (0-32767 range)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "device_id": {
                    "type": "string",
                    "description": "ID of the KVM device",
                },
                "x": {
                    "type": "integer",
                    "description": "X coordinate (0-32767, where 16383 is center)",
                },
                "y": {
                    "type": "integer",
                    "description": "Y coordinate (0-32767, where 16383 is center)",
                },
            },
            "required": ["device_id", "x", "y"],
        },
    },
    {
        "name": "kvm_mouse_click",
        "description": "Click a mouse button, optionally at specific coordinates",
        "inputSchema": {
            "type": "object",
            "properties": {
                "device_id": {
                    "type": "string",
                    "description": "ID of the KVM device",
                },
                "button": {
                    "type": "string",
                    "enum": ["left", "right", "middle"],
                    "description": "Mouse button to click (default: left)",
                },
                "x": {
                    "type": "integer",
                    "description": "X coordinate to click at (0-32767)",
                },
                "y": {
                    "type": "integer",
                    "description": "Y coordinate to click at (0-32767)",
                },
                "double": {
                    "type": "boolean",
                    "description": "Whether to double-click (default: false)",
                },
            },
            "required": ["device_id"],
        },
    },
    {
        "name": "kvm_mouse_scroll",
        "description": "Scroll the mouse wheel",
        "inputSchema": {
            "type": "object",
            "properties": {
                "device_id": {
                    "type": "string",
                    "description": "ID of the KVM device",
                },
                "amount": {
                    "type": "integer",
                    "description": "Scroll amount (positive = up, negative = down, range: -127 to 127)",
                },
            },
            "required": ["device_id", "amount"],
        },
    },
    {
        "name": "kvm_keyboard_type",
        "description": "Type a string of text",
        "inputSchema": {
            "type": "object",
            "properties": {
                "device_id": {
                    "type": "string",
                    "description": "ID of the KVM device",
                },
                "text": {
                    "type": "string",
                    "description": "Text to type",
                },
            },
            "required": ["device_id", "text"],
        },
    },
    {
        "name": "kvm_keyboard_press",
        "description": "Press a key or key combination (e.g., 'enter', 'f1', 'a' with modifiers ['ctrl'])",
        "inputSchema": {
            "type": "object",
            "properties": {
                "device_id": {
                    "type": "string",
                    "description": "ID of the KVM device",
                },
                "key": {
                    "type": "string",
                    "description": "Key to press (e.g., 'enter', 'tab', 'f1', 'a')",
                },
                "modifiers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Modifier keys (e.g., ['ctrl'], ['ctrl', 'shift'])",
                },
            },
            "required": ["device_id", "key"],
        },
    },
]


class ToolHandler:
    """Handles MCP tool calls."""

    def __init__(self, config: Config, client: KVMClient):
        self.config = config
        self.client = client

    def handle(self, name: str, arguments: dict) -> Any:
        """Handle a tool call and return the result."""
        handler = getattr(self, f"_handle_{name}", None)
        if handler is None:
            raise ValueError(f"Unknown tool: {name}")
        return handler(arguments)

    def _handle_kvm_list_devices(self, args: dict) -> dict:
        """List all configured devices."""
        devices = self.config.list_devices()
        return {
            "devices": [
                {
                    "device_id": d.device_id,
                    "ip": d.ip,
                    "port": d.port,
                    "name": d.name,
                    "url": d.url,
                }
                for d in devices
            ]
        }

    def _handle_kvm_add_device(self, args: dict) -> dict:
        """Add a new device."""
        device = self.config.add_device(
            device_id=args["device_id"],
            ip=args["ip"],
            port=args.get("port"),
            name=args.get("name"),
        )
        return {
            "success": True,
            "device": {
                "device_id": device.device_id,
                "ip": device.ip,
                "port": device.port,
                "name": device.name,
            },
        }

    def _handle_kvm_remove_device(self, args: dict) -> dict:
        """Remove a device."""
        removed = self.config.remove_device(args["device_id"])
        return {
            "success": removed,
            "message": "Device removed" if removed else "Device not found",
        }

    def _handle_kvm_capture_screen(self, args: dict) -> dict:
        """Capture a screenshot."""
        device_id = args["device_id"]
        max_width = args.get("max_width", 1280)
        max_height = args.get("max_height", 720)
        quality = args.get("quality", 70)

        h264_data = self.client.capture_screenshot(device_id)
        jpeg_data, resized_image, original_image = process_screenshot(
            h264_data, max_width=max_width, max_height=max_height, quality=quality
        )

        return {
            "image": base64.b64encode(jpeg_data).decode(),
            "width": resized_image.width,
            "height": resized_image.height,
            "original_width": original_image.width,
            "original_height": original_image.height,
            "format": "jpeg",
        }

    def _handle_kvm_screenshot_with_ocr(self, args: dict) -> dict:
        """Capture screenshot with OCR."""
        device_id = args["device_id"]
        max_width = args.get("max_width", 1280)
        max_height = args.get("max_height", 720)
        quality = args.get("quality", 70)

        h264_data = self.client.capture_screenshot(device_id)

        # Get resized image for return, but OCR uses original for accuracy
        jpeg_data, resized_image, original_image = process_screenshot(
            h264_data, max_width=max_width, max_height=max_height, quality=quality
        )
        ocr_result, _ = ocr_screenshot(h264_data)

        return {
            "image": base64.b64encode(jpeg_data).decode(),
            "width": resized_image.width,
            "height": resized_image.height,
            "original_width": original_image.width,
            "original_height": original_image.height,
            "format": "jpeg",
            "text": ocr_result.text,
            "boxes": ocr_result.boxes,
        }

    def _handle_kvm_find_and_click(self, args: dict) -> dict:
        """Find text and optionally click it."""
        device_id = args["device_id"]
        search_text = args["text"]
        should_click = args.get("click", True)

        # Get screenshot and OCR (uses original image for accuracy)
        h264_data = self.client.capture_screenshot(device_id)
        ocr_result, original_image = ocr_screenshot(h264_data)

        # Find matching text
        matches = find_text(ocr_result.boxes, search_text)

        result = {
            "search_text": search_text,
            "matches_found": len(matches),
            "matches": matches,
            "screen_width": original_image.width,
            "screen_height": original_image.height,
            "clicked": False,
        }

        # Click if single match and clicking enabled
        if len(matches) == 1 and should_click:
            match = matches[0]
            hid_x, hid_y = pixel_to_hid(
                match["center_x"],
                match["center_y"],
                original_image.width,
                original_image.height,
            )
            self.client.mouse_click(device_id, x=hid_x, y=hid_y)
            result["clicked"] = True
            result["clicked_at"] = {"hid_x": hid_x, "hid_y": hid_y}
        elif len(matches) > 1:
            result["message"] = "Multiple matches found - specify which one to click"
        elif len(matches) == 0:
            result["message"] = "No matches found"

        return result

    def _handle_kvm_mouse_move(self, args: dict) -> dict:
        """Move mouse cursor."""
        return self.client.mouse_move(args["device_id"], args["x"], args["y"])

    def _handle_kvm_mouse_click(self, args: dict) -> dict:
        """Click mouse button."""
        return self.client.mouse_click(
            device_id=args["device_id"],
            button=args.get("button", "left"),
            double=args.get("double", False),
            x=args.get("x"),
            y=args.get("y"),
        )

    def _handle_kvm_mouse_scroll(self, args: dict) -> dict:
        """Scroll mouse wheel."""
        return self.client.mouse_scroll(args["device_id"], args["amount"])

    def _handle_kvm_keyboard_type(self, args: dict) -> dict:
        """Type text."""
        return self.client.keyboard_type(args["device_id"], args["text"])

    def _handle_kvm_keyboard_press(self, args: dict) -> dict:
        """Press key combination."""
        return self.client.keyboard_press(
            device_id=args["device_id"],
            key=args["key"],
            modifiers=args.get("modifiers"),
        )
