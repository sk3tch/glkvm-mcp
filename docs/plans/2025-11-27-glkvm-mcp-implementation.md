# GLKVM MCP Server Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build an all-Python MCP server that controls KVM devices directly over HTTPS with mTLS authentication.

**Architecture:** Local Python MCP server communicates via stdio with Claude Code, connects to HID servers on KVM devices over HTTPS with client certificates. Tesseract runs locally for OCR.

**Tech Stack:** Python 3.10+, pytesseract, Pillow, PyYAML, ssl, http.server

---

## Task 1: Project Scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `requirements.txt`
- Create: `.gitignore`
- Create: `config.example.yaml`
- Create: `src/glkvm_mcp/__init__.py`

**Step 1: Create pyproject.toml**

```toml
[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"

[project]
name = "glkvm-mcp"
version = "0.1.0"
description = "MCP server for controlling KVM devices"
readme = "README.md"
requires-python = ">=3.10"
license = {text = "MIT"}
authors = [
    {name = "Dave King", email = "dave@davewking.com"}
]
dependencies = [
    "pytesseract>=0.3.10",
    "Pillow>=10.0.0",
    "PyYAML>=6.0",
]

[project.scripts]
glkvm-mcp = "glkvm_mcp.server:main"

[tool.setuptools.packages.find]
where = ["src"]
```

**Step 2: Create requirements.txt**

```
pytesseract>=0.3.10
Pillow>=10.0.0
PyYAML>=6.0
```

**Step 3: Create .gitignore**

```
# Config with real data
config.yaml

# Certificates
*.crt
*.key
*.pem
*.csr
certs/

# Python
__pycache__/
*.pyc
*.pyo
*.egg-info/
dist/
build/
.eggs/

# Environment
.env
.venv/
venv/

# IDE
.idea/
.vscode/
*.swp

# OS
.DS_Store
Thumbs.db
```

**Step 4: Create config.example.yaml**

```yaml
# GLKVM MCP Server Configuration
# Copy to ~/.config/glkvm-mcp/config.yaml and customize

# Certificate directory (optional, defaults shown)
# Can also set via GLKVM_CERTS_DIR environment variable
certs_dir: ~/.config/glkvm-mcp/certs

# Default port for KVM devices
default_port: 8443

# KVM devices
devices:
  # Example device - replace with your actual KVMs
  kvm-example:
    ip: 192.168.1.100
    port: 8443              # optional, uses default_port
    name: "Example KVM"     # optional friendly name
```

**Step 5: Create src/glkvm_mcp/__init__.py**

```python
"""GLKVM MCP Server - Control KVM devices via MCP protocol."""

__version__ = "0.1.0"
```

**Step 6: Create directory structure**

Run:
```bash
mkdir -p src/glkvm_mcp kvm scripts
touch src/glkvm_mcp/__init__.py
```

**Step 7: Verify structure**

Run:
```bash
ls -la src/glkvm_mcp/ kvm/ scripts/
```

Expected: Directories exist with __init__.py in src/glkvm_mcp/

**Step 8: Commit**

```bash
git add -A
git commit -m "chore: initial project scaffolding"
```

---

## Task 2: Configuration Module

**Files:**
- Create: `src/glkvm_mcp/config.py`

**Step 1: Create config.py**

```python
"""Configuration loading and management."""

import os
from pathlib import Path
from typing import Optional
import yaml


DEFAULT_CONFIG_PATH = Path.home() / ".config" / "glkvm-mcp" / "config.yaml"
DEFAULT_CERTS_DIR = Path.home() / ".config" / "glkvm-mcp" / "certs"
DEFAULT_PORT = 8443


class Device:
    """Represents a KVM device."""

    def __init__(self, device_id: str, ip: str, port: int = DEFAULT_PORT, name: Optional[str] = None):
        self.device_id = device_id
        self.ip = ip
        self.port = port
        self.name = name or device_id

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        d = {"ip": self.ip}
        if self.port != DEFAULT_PORT:
            d["port"] = self.port
        if self.name != self.device_id:
            d["name"] = self.name
        return d

    @property
    def url(self) -> str:
        """Get the base URL for this device."""
        return f"https://{self.ip}:{self.port}"


class Config:
    """Configuration manager."""

    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or Path(os.environ.get("GLKVM_CONFIG", DEFAULT_CONFIG_PATH))
        self.certs_dir = Path(os.environ.get("GLKVM_CERTS_DIR", DEFAULT_CERTS_DIR))
        self.default_port = DEFAULT_PORT
        self.devices: dict[str, Device] = {}

        self._load()

    def _load(self) -> None:
        """Load configuration from file."""
        if not self.config_path.exists():
            return

        with open(self.config_path) as f:
            data = yaml.safe_load(f) or {}

        # Load certs_dir
        if "certs_dir" in data:
            self.certs_dir = Path(data["certs_dir"]).expanduser()

        # Load default port
        if "default_port" in data:
            self.default_port = int(data["default_port"])

        # Load devices
        for device_id, device_data in data.get("devices", {}).items():
            self.devices[device_id] = Device(
                device_id=device_id,
                ip=device_data["ip"],
                port=device_data.get("port", self.default_port),
                name=device_data.get("name"),
            )

    def save(self) -> None:
        """Save configuration to file."""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "certs_dir": str(self.certs_dir),
            "default_port": self.default_port,
            "devices": {
                device_id: device.to_dict()
                for device_id, device in self.devices.items()
            },
        }

        with open(self.config_path, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)

    def get_device(self, device_id: str) -> Optional[Device]:
        """Get a device by ID."""
        return self.devices.get(device_id)

    def add_device(self, device_id: str, ip: str, port: Optional[int] = None, name: Optional[str] = None) -> Device:
        """Add a new device."""
        device = Device(
            device_id=device_id,
            ip=ip,
            port=port or self.default_port,
            name=name,
        )
        self.devices[device_id] = device
        self.save()
        return device

    def remove_device(self, device_id: str) -> bool:
        """Remove a device. Returns True if removed, False if not found."""
        if device_id in self.devices:
            del self.devices[device_id]
            self.save()
            return True
        return False

    def list_devices(self) -> list[Device]:
        """List all devices."""
        return list(self.devices.values())

    @property
    def ca_cert_path(self) -> Path:
        """Path to CA certificate."""
        return self.certs_dir / "ca.crt"

    @property
    def client_cert_path(self) -> Path:
        """Path to client certificate."""
        return self.certs_dir / "client.crt"

    @property
    def client_key_path(self) -> Path:
        """Path to client private key."""
        return self.certs_dir / "client.key"
```

**Step 2: Verify syntax**

Run:
```bash
python3 -m py_compile src/glkvm_mcp/config.py
```

Expected: No output (success)

**Step 3: Commit**

```bash
git add src/glkvm_mcp/config.py
git commit -m "feat: add configuration module"
```

---

## Task 3: KVM Client Module

**Files:**
- Create: `src/glkvm_mcp/client.py`

**Step 1: Create client.py**

```python
"""HTTPS client for communicating with KVM HID servers."""

import json
import ssl
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional, Any

from .config import Config, Device


class KVMClientError(Exception):
    """Error communicating with KVM device."""
    pass


class KVMClient:
    """Client for communicating with a KVM HID server over mTLS."""

    def __init__(self, config: Config):
        self.config = config
        self._ssl_context: Optional[ssl.SSLContext] = None

    def _get_ssl_context(self) -> ssl.SSLContext:
        """Get or create SSL context with client certificates."""
        if self._ssl_context is None:
            self._ssl_context = ssl.create_default_context(
                purpose=ssl.Purpose.SERVER_AUTH,
                cafile=str(self.config.ca_cert_path),
            )
            self._ssl_context.load_cert_chain(
                certfile=str(self.config.client_cert_path),
                keyfile=str(self.config.client_key_path),
            )
        return self._ssl_context

    def _request(self, device: Device, method: str, path: str, data: Optional[dict] = None) -> Any:
        """Make an HTTP request to the KVM device."""
        url = f"{device.url}{path}"

        headers = {"Content-Type": "application/json"} if data else {}
        body = json.dumps(data).encode() if data else None

        request = urllib.request.Request(url, data=body, headers=headers, method=method)

        try:
            with urllib.request.urlopen(request, context=self._get_ssl_context(), timeout=30) as response:
                content_type = response.headers.get("Content-Type", "")
                if "application/json" in content_type:
                    return json.loads(response.read().decode())
                else:
                    return response.read()
        except urllib.error.HTTPError as e:
            try:
                error_body = json.loads(e.read().decode())
                raise KVMClientError(f"HTTP {e.code}: {error_body.get('error', str(e))}")
            except json.JSONDecodeError:
                raise KVMClientError(f"HTTP {e.code}: {e.reason}")
        except urllib.error.URLError as e:
            raise KVMClientError(f"Connection failed: {e.reason}")
        except ssl.SSLError as e:
            raise KVMClientError(f"SSL error: {e}")

    def _get_device(self, device_id: str) -> Device:
        """Get device by ID, raising error if not found."""
        device = self.config.get_device(device_id)
        if device is None:
            raise KVMClientError(f"Device not found: {device_id}")
        return device

    def health_check(self, device_id: str) -> dict:
        """Check if device is healthy."""
        device = self._get_device(device_id)
        return self._request(device, "GET", "/health")

    def capture_screenshot(self, device_id: str) -> bytes:
        """Capture screenshot from device. Returns H.264 data."""
        device = self._get_device(device_id)
        return self._request(device, "GET", "/screenshot")

    def mouse_move(self, device_id: str, x: int, y: int) -> dict:
        """Move mouse to absolute coordinates (0-32767)."""
        device = self._get_device(device_id)
        return self._request(device, "POST", "/mouse/move", {"x": x, "y": y})

    def mouse_click(
        self,
        device_id: str,
        button: str = "left",
        double: bool = False,
        x: Optional[int] = None,
        y: Optional[int] = None,
    ) -> dict:
        """Click mouse button."""
        device = self._get_device(device_id)
        data = {"button": button, "double": double}
        if x is not None:
            data["x"] = x
        if y is not None:
            data["y"] = y
        return self._request(device, "POST", "/mouse/click", data)

    def mouse_scroll(self, device_id: str, amount: int) -> dict:
        """Scroll mouse wheel. Positive = up, negative = down."""
        device = self._get_device(device_id)
        return self._request(device, "POST", "/mouse/scroll", {"amount": amount})

    def keyboard_type(self, device_id: str, text: str) -> dict:
        """Type a string of text."""
        device = self._get_device(device_id)
        return self._request(device, "POST", "/keyboard/type", {"text": text})

    def keyboard_press(self, device_id: str, key: str, modifiers: Optional[list[str]] = None) -> dict:
        """Press a key or key combination."""
        device = self._get_device(device_id)
        data = {"key": key}
        if modifiers:
            data["modifiers"] = modifiers
        return self._request(device, "POST", "/keyboard/press", data)
```

**Step 2: Verify syntax**

Run:
```bash
python3 -m py_compile src/glkvm_mcp/client.py
```

Expected: No output (success)

**Step 3: Commit**

```bash
git add src/glkvm_mcp/client.py
git commit -m "feat: add KVM client module with mTLS support"
```

---

## Task 4: OCR Module

**Files:**
- Create: `src/glkvm_mcp/ocr.py`

**Step 1: Create ocr.py**

```python
"""OCR processing using Tesseract."""

import io
import subprocess
from typing import Optional

from PIL import Image
import pytesseract


class OCRError(Exception):
    """Error during OCR processing."""
    pass


class OCRResult:
    """Result of OCR processing."""

    def __init__(self, text: str, boxes: list[dict]):
        self.text = text
        self.boxes = boxes  # List of {word, x, y, width, height, confidence}


def h264_to_jpeg(h264_data: bytes) -> bytes:
    """Convert H.264 keyframes to JPEG using ffmpeg."""
    try:
        result = subprocess.run(
            [
                "ffmpeg",
                "-f", "h264",
                "-i", "pipe:0",
                "-vframes", "1",
                "-f", "image2",
                "-c:v", "mjpeg",
                "-q:v", "2",
                "pipe:1",
            ],
            input=h264_data,
            capture_output=True,
            timeout=10,
        )
        if result.returncode != 0:
            raise OCRError(f"ffmpeg failed: {result.stderr.decode()}")
        return result.stdout
    except FileNotFoundError:
        raise OCRError("ffmpeg not found - please install ffmpeg")
    except subprocess.TimeoutExpired:
        raise OCRError("ffmpeg timed out")


def process_screenshot(h264_data: bytes) -> tuple[bytes, Image.Image]:
    """Convert H.264 to JPEG and return both bytes and PIL Image."""
    jpeg_data = h264_to_jpeg(h264_data)
    image = Image.open(io.BytesIO(jpeg_data))
    return jpeg_data, image


def extract_text(image: Image.Image) -> str:
    """Extract text from image using Tesseract."""
    try:
        return pytesseract.image_to_string(image)
    except pytesseract.TesseractNotFoundError:
        raise OCRError("Tesseract not found - please install tesseract-ocr")


def extract_boxes(image: Image.Image) -> list[dict]:
    """Extract text with bounding boxes from image."""
    try:
        data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
    except pytesseract.TesseractNotFoundError:
        raise OCRError("Tesseract not found - please install tesseract-ocr")

    boxes = []
    for i, word in enumerate(data["text"]):
        if word.strip():
            boxes.append({
                "word": word,
                "x": data["left"][i],
                "y": data["top"][i],
                "width": data["width"][i],
                "height": data["height"][i],
                "confidence": data["conf"][i],
            })
    return boxes


def ocr_screenshot(h264_data: bytes) -> OCRResult:
    """Process screenshot and extract text with bounding boxes."""
    _, image = process_screenshot(h264_data)
    text = extract_text(image)
    boxes = extract_boxes(image)
    return OCRResult(text=text, boxes=boxes)


def find_text(boxes: list[dict], search_text: str) -> list[dict]:
    """Find text in OCR boxes. Returns matching boxes with center coordinates."""
    search_lower = search_text.lower()
    matches = []

    for box in boxes:
        if search_lower in box["word"].lower():
            # Calculate center point
            center_x = box["x"] + box["width"] // 2
            center_y = box["y"] + box["height"] // 2
            matches.append({
                **box,
                "center_x": center_x,
                "center_y": center_y,
            })

    return matches


def pixel_to_hid(pixel_x: int, pixel_y: int, screen_width: int, screen_height: int) -> tuple[int, int]:
    """Convert pixel coordinates to HID coordinates (0-32767)."""
    hid_x = int((pixel_x / screen_width) * 32767)
    hid_y = int((pixel_y / screen_height) * 32767)
    return hid_x, hid_y
```

**Step 2: Verify syntax**

Run:
```bash
python3 -m py_compile src/glkvm_mcp/ocr.py
```

Expected: No output (success)

**Step 3: Commit**

```bash
git add src/glkvm_mcp/ocr.py
git commit -m "feat: add OCR module with Tesseract integration"
```

---

## Task 5: MCP Tools Module

**Files:**
- Create: `src/glkvm_mcp/tools.py`

**Step 1: Create tools.py**

```python
"""MCP tool definitions and handlers."""

import base64
import io
from typing import Any, Optional

from PIL import Image

from .config import Config
from .client import KVMClient, KVMClientError
from .ocr import (
    OCRError,
    process_screenshot,
    ocr_screenshot,
    find_text,
    pixel_to_hid,
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
        h264_data = self.client.capture_screenshot(device_id)
        jpeg_data, image = process_screenshot(h264_data)

        return {
            "image": base64.b64encode(jpeg_data).decode(),
            "width": image.width,
            "height": image.height,
            "format": "jpeg",
        }

    def _handle_kvm_screenshot_with_ocr(self, args: dict) -> dict:
        """Capture screenshot with OCR."""
        device_id = args["device_id"]
        h264_data = self.client.capture_screenshot(device_id)
        jpeg_data, image = process_screenshot(h264_data)
        ocr_result = ocr_screenshot(h264_data)

        return {
            "image": base64.b64encode(jpeg_data).decode(),
            "width": image.width,
            "height": image.height,
            "format": "jpeg",
            "text": ocr_result.text,
            "boxes": ocr_result.boxes,
        }

    def _handle_kvm_find_and_click(self, args: dict) -> dict:
        """Find text and optionally click it."""
        device_id = args["device_id"]
        search_text = args["text"]
        should_click = args.get("click", True)

        # Get screenshot and OCR
        h264_data = self.client.capture_screenshot(device_id)
        jpeg_data, image = process_screenshot(h264_data)
        ocr_result = ocr_screenshot(h264_data)

        # Find matching text
        matches = find_text(ocr_result.boxes, search_text)

        result = {
            "search_text": search_text,
            "matches_found": len(matches),
            "matches": matches,
            "screen_width": image.width,
            "screen_height": image.height,
            "clicked": False,
        }

        # Click if single match and clicking enabled
        if len(matches) == 1 and should_click:
            match = matches[0]
            hid_x, hid_y = pixel_to_hid(
                match["center_x"],
                match["center_y"],
                image.width,
                image.height,
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
```

**Step 2: Verify syntax**

Run:
```bash
python3 -m py_compile src/glkvm_mcp/tools.py
```

Expected: No output (success)

**Step 3: Commit**

```bash
git add src/glkvm_mcp/tools.py
git commit -m "feat: add MCP tools module with all tool handlers"
```

---

## Task 6: MCP Server Module

**Files:**
- Create: `src/glkvm_mcp/server.py`

**Step 1: Create server.py**

```python
"""MCP server implementation using stdio transport."""

import json
import sys
from typing import Any, Optional

from .config import Config
from .client import KVMClient, KVMClientError
from .tools import TOOLS, ToolHandler
from .ocr import OCRError


# MCP Protocol version
PROTOCOL_VERSION = "2024-11-05"

# Server info
SERVER_NAME = "glkvm-mcp"
SERVER_VERSION = "0.1.0"


def read_message() -> Optional[dict]:
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
        return make_response(id, {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {
                "tools": {},
            },
            "serverInfo": {
                "name": SERVER_NAME,
                "version": SERVER_VERSION,
            },
        })

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
            return make_response(id, {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(result, indent=2),
                    }
                ],
            })
        except KVMClientError as e:
            return make_response(id, {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps({"error": str(e)}),
                    }
                ],
                "isError": True,
            })
        except OCRError as e:
            return make_response(id, {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps({"error": f"OCR error: {e}"}),
                    }
                ],
                "isError": True,
            })
        except Exception as e:
            return make_response(id, {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps({"error": f"Unexpected error: {e}"}),
                    }
                ],
                "isError": True,
            })

    def handle_message(self, message: dict) -> Optional[dict]:
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
```

**Step 2: Verify syntax**

Run:
```bash
python3 -m py_compile src/glkvm_mcp/server.py
```

Expected: No output (success)

**Step 3: Commit**

```bash
git add src/glkvm_mcp/server.py
git commit -m "feat: add MCP server with stdio transport"
```

---

## Task 7: HID Server for KVM Device

**Files:**
- Create: `kvm/hid_server.py`

**Step 1: Copy and adapt HID server**

Copy the existing HID server from `/home/davewking/glkvm-cloud/mcp-proxy/scripts/kvm-hid-server.py` to `kvm/hid_server.py`. The file is already complete and tested - no modifications needed.

Run:
```bash
cp /home/davewking/glkvm-cloud/mcp-proxy/scripts/kvm-hid-server.py kvm/hid_server.py
chmod +x kvm/hid_server.py
```

**Step 2: Verify it's executable**

Run:
```bash
head -1 kvm/hid_server.py
```

Expected: `#!/usr/bin/env python3`

**Step 3: Commit**

```bash
git add kvm/hid_server.py
git commit -m "feat: add HID server for KVM devices"
```

---

## Task 8: Certificate Generation Script

**Files:**
- Create: `scripts/generate_certs.sh`

**Step 1: Create generate_certs.sh**

```bash
#!/bin/bash
# Generate CA and client certificates for GLKVM MCP
# Run once on your local machine

set -e

# Default paths
CERTS_DIR="${GLKVM_CERTS_DIR:-$HOME/.config/glkvm-mcp/certs}"

# Certificate validity (10 years)
DAYS=3650

echo "=== GLKVM Certificate Generator ==="
echo ""
echo "This will create certificates in: $CERTS_DIR"
echo ""

# Create directory
mkdir -p "$CERTS_DIR"
cd "$CERTS_DIR"

# Check if CA already exists
if [ -f "ca.crt" ]; then
    echo "Warning: CA certificate already exists!"
    read -p "Overwrite? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Aborted."
        exit 1
    fi
fi

echo "Step 1: Generating CA private key..."
openssl genrsa -out ca.key 4096

echo "Step 2: Creating CA certificate..."
openssl req -new -x509 -days $DAYS -key ca.key -out ca.crt \
    -subj "/CN=GLKVM CA/O=GLKVM"

echo "Step 3: Generating client private key..."
openssl genrsa -out client.key 4096

echo "Step 4: Creating client certificate signing request..."
openssl req -new -key client.key -out client.csr \
    -subj "/CN=GLKVM Client/O=GLKVM"

echo "Step 5: Signing client certificate with CA..."
openssl x509 -req -days $DAYS -in client.csr -CA ca.crt -CAkey ca.key \
    -CAcreateserial -out client.crt

# Clean up CSR
rm -f client.csr

# Set permissions
chmod 600 ca.key client.key
chmod 644 ca.crt client.crt

echo ""
echo "=== Certificates Generated ==="
echo ""
echo "Files created in $CERTS_DIR:"
echo "  ca.crt      - CA certificate (copy to KVM devices)"
echo "  ca.key      - CA private key (keep secure, used to sign KVM certs)"
echo "  client.crt  - Client certificate (used by MCP server)"
echo "  client.key  - Client private key (used by MCP server)"
echo ""
echo "Next steps:"
echo "  1. Run setup_kvm.sh on each KVM device"
echo "  2. When prompted, paste the contents of ca.crt"
echo ""
```

**Step 2: Make executable**

Run:
```bash
chmod +x scripts/generate_certs.sh
```

**Step 3: Verify**

Run:
```bash
bash -n scripts/generate_certs.sh
```

Expected: No output (valid syntax)

**Step 4: Commit**

```bash
git add scripts/generate_certs.sh
git commit -m "feat: add certificate generation script"
```

---

## Task 9: KVM Setup Script

**Files:**
- Create: `scripts/setup_kvm.sh`

**Step 1: Create setup_kvm.sh**

```bash
#!/bin/bash
# Setup script for GLKVM HID Server on KVM devices
# Download and run: curl -sSL https://raw.githubusercontent.com/davewking/glkvm-mcp/main/scripts/setup_kvm.sh | bash

set -e

GLKVM_DIR="/etc/glkvm"
CERTS_DIR="$GLKVM_DIR/certs"
HID_SERVER_URL="https://raw.githubusercontent.com/davewking/glkvm-mcp/main/kvm/hid_server.py"
SERVICE_NAME="glkvm-hid"

echo "=== GLKVM HID Server Setup ==="
echo ""

# Check for root
if [ "$EUID" -ne 0 ]; then
    echo "Please run as root (sudo)"
    exit 1
fi

# Step 1: Device ID
echo "Step 1: Device ID"
read -p "  Enter a unique ID for this KVM (e.g., kvm-office): " DEVICE_ID

if [ -z "$DEVICE_ID" ]; then
    echo "Error: Device ID cannot be empty"
    exit 1
fi

# Create directories
mkdir -p "$CERTS_DIR"

# Step 2: CA Certificate
echo ""
echo "Step 2: CA Certificate"
echo "  Paste your CA certificate (from ~/.config/glkvm-mcp/certs/ca.crt)"
echo "  End with an empty line:"
echo ""

CA_CERT=""
while IFS= read -r line; do
    [ -z "$line" ] && break
    CA_CERT="${CA_CERT}${line}"$'\n'
done

echo "$CA_CERT" > "$CERTS_DIR/ca.crt"
echo "  ✓ CA certificate saved to $CERTS_DIR/ca.crt"

# Step 3: Generate server certificate
echo ""
echo "Step 3: Generate Server Certificate"
echo "  Generating server key and CSR..."

openssl genrsa -out "$CERTS_DIR/server.key" 4096 2>/dev/null
openssl req -new -key "$CERTS_DIR/server.key" -out "$CERTS_DIR/server.csr" \
    -subj "/CN=$DEVICE_ID/O=GLKVM" 2>/dev/null

echo "  ✓ Server key saved to $CERTS_DIR/server.key"
echo ""
echo "  === ACTION REQUIRED ==="
echo "  Run this on your LOCAL machine to sign the certificate:"
echo ""
echo "  echo '$(cat "$CERTS_DIR/server.csr")' | \\"
echo "  openssl x509 -req -CA ~/.config/glkvm-mcp/certs/ca.crt \\"
echo "    -CAkey ~/.config/glkvm-mcp/certs/ca.key \\"
echo "    -CAcreateserial -days 3650 -out /dev/stdout 2>/dev/null"
echo ""
echo "  Then paste the signed certificate here (end with empty line):"
echo ""

SERVER_CERT=""
while IFS= read -r line; do
    [ -z "$line" ] && break
    SERVER_CERT="${SERVER_CERT}${line}"$'\n'
done

echo "$SERVER_CERT" > "$CERTS_DIR/server.crt"
rm -f "$CERTS_DIR/server.csr"
echo "  ✓ Server certificate saved to $CERTS_DIR/server.crt"

# Set permissions
chmod 600 "$CERTS_DIR/server.key"
chmod 644 "$CERTS_DIR/ca.crt" "$CERTS_DIR/server.crt"

# Step 4: Install HID Server
echo ""
echo "Step 4: Install HID Server"
echo "  Downloading hid_server.py..."

curl -sSL "$HID_SERVER_URL" -o /usr/local/bin/glkvm-hid-server
chmod +x /usr/local/bin/glkvm-hid-server

echo "  ✓ Installed to /usr/local/bin/glkvm-hid-server"

# Step 5: Create systemd service
echo ""
echo "Step 5: Create systemd service"

cat > "/etc/systemd/system/${SERVICE_NAME}.service" << EOF
[Unit]
Description=GLKVM HID Server
After=network.target

[Service]
Type=simple
ExecStart=/usr/local/bin/glkvm-hid-server --port 8443 --tls --cert $CERTS_DIR/server.crt --key $CERTS_DIR/server.key --ca $CERTS_DIR/ca.crt
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable "$SERVICE_NAME"
systemctl start "$SERVICE_NAME"

echo "  ✓ Created and started $SERVICE_NAME service"

# Get IP address
IP_ADDR=$(hostname -I | awk '{print $1}')

echo ""
echo "=== Setup Complete ==="
echo ""
echo "  Device ID: $DEVICE_ID"
echo "  Listening: https://0.0.0.0:8443"
echo "  IP Address: $IP_ADDR"
echo ""
echo "  Add to your local ~/.config/glkvm-mcp/config.yaml:"
echo ""
echo "  devices:"
echo "    $DEVICE_ID:"
echo "      ip: $IP_ADDR"
echo "      name: \"$DEVICE_ID\""
echo ""
echo "  To check status: systemctl status $SERVICE_NAME"
echo "  To view logs: journalctl -u $SERVICE_NAME -f"
echo ""
```

**Step 2: Make executable**

Run:
```bash
chmod +x scripts/setup_kvm.sh
```

**Step 3: Verify syntax**

Run:
```bash
bash -n scripts/setup_kvm.sh
```

Expected: No output (valid syntax)

**Step 4: Commit**

```bash
git add scripts/setup_kvm.sh
git commit -m "feat: add KVM setup script"
```

---

## Task 10: README Documentation

**Files:**
- Create: `README.md`

**Step 1: Create README.md**

```markdown
# GLKVM MCP Server

A Python MCP server for controlling KVM devices directly over HTTPS with mutual TLS (client certificate) authentication.

## Features

- **Direct connection** - No proxy server, connects directly to KVM devices
- **mTLS authentication** - Client certificates for secure access
- **10 MCP tools** - Screenshot, mouse, keyboard, OCR, device management
- **Local OCR** - Tesseract runs locally, no cloud APIs needed
- **Simple setup** - One script to provision new KVM devices

## Prerequisites

### Local Machine (where MCP server runs)

- Python 3.10+
- Tesseract OCR: `apt install tesseract-ocr` or `brew install tesseract`
- ffmpeg: `apt install ffmpeg` or `brew install ffmpeg`

### KVM Device

- Linux with USB HID gadget support (GL.iNet, Raspberry Pi, etc.)
- ustreamer running for video capture
- Python 3

## Installation

```bash
# Clone the repository
git clone https://github.com/davewking/glkvm-mcp.git
cd glkvm-mcp

# Install Python dependencies
pip install -r requirements.txt

# Generate certificates (one-time)
./scripts/generate_certs.sh
```

## KVM Device Setup

On each KVM device:

```bash
curl -sSL https://raw.githubusercontent.com/davewking/glkvm-mcp/main/scripts/setup_kvm.sh | sudo bash
```

The script will:
1. Ask for a device ID
2. Ask for your CA certificate
3. Generate a server certificate (you'll sign it with your CA)
4. Install and start the HID server

## Configuration

Create `~/.config/glkvm-mcp/config.yaml`:

```yaml
devices:
  kvm-office:
    ip: 192.168.1.31
    name: "Office PC"

  kvm-server:
    ip: 192.168.1.32
    name: "Home Server"
```

## Usage with Claude Code

Add to your Claude Code MCP settings:

```json
{
  "mcpServers": {
    "glkvm": {
      "command": "python",
      "args": ["-m", "glkvm_mcp.server"],
      "cwd": "/path/to/glkvm-mcp/src"
    }
  }
}
```

Or if installed as a package:

```json
{
  "mcpServers": {
    "glkvm": {
      "command": "glkvm-mcp"
    }
  }
}
```

## Available Tools

| Tool | Description |
|------|-------------|
| `kvm_list_devices` | List all configured KVM devices |
| `kvm_add_device` | Add a new KVM device |
| `kvm_remove_device` | Remove a KVM device |
| `kvm_capture_screen` | Capture screenshot (base64 JPEG) |
| `kvm_screenshot_with_ocr` | Screenshot + OCR text extraction |
| `kvm_find_and_click` | Find text on screen and click it |
| `kvm_mouse_move` | Move cursor (0-32767 coordinates) |
| `kvm_mouse_click` | Click mouse button |
| `kvm_mouse_scroll` | Scroll mouse wheel |
| `kvm_keyboard_type` | Type text string |
| `kvm_keyboard_press` | Press key/combo (e.g., Ctrl+C) |

## License

MIT
```

**Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add README with setup instructions"
```

---

## Task 11: Final Integration Test

**Step 1: Verify all files exist**

Run:
```bash
find . -type f -name "*.py" -o -name "*.sh" -o -name "*.yaml" -o -name "*.toml" -o -name "*.txt" -o -name "*.md" | grep -v __pycache__ | sort
```

Expected:
```
./config.example.yaml
./docs/plans/2025-11-27-glkvm-mcp-design.md
./docs/plans/2025-11-27-glkvm-mcp-implementation.md
./kvm/hid_server.py
./pyproject.toml
./README.md
./requirements.txt
./scripts/generate_certs.sh
./scripts/setup_kvm.sh
./src/glkvm_mcp/__init__.py
./src/glkvm_mcp/client.py
./src/glkvm_mcp/config.py
./src/glkvm_mcp/ocr.py
./src/glkvm_mcp/server.py
./src/glkvm_mcp/tools.py
```

**Step 2: Verify Python imports**

Run:
```bash
cd src && python3 -c "from glkvm_mcp import server; print('Imports OK')"
```

Expected: `Imports OK`

**Step 3: Test MCP server starts**

Run:
```bash
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' | python3 -m glkvm_mcp.server 2>/dev/null | head -1
```

Expected: JSON response with `protocolVersion`

**Step 4: Final commit**

```bash
git add -A
git commit -m "feat: complete GLKVM MCP server implementation"
```

---

## Summary

After completing all tasks, you will have:

1. **Project structure** with proper Python packaging
2. **Config module** for device management with YAML persistence
3. **Client module** for mTLS communication with KVM devices
4. **OCR module** with Tesseract integration
5. **Tools module** with 10 MCP tools
6. **Server module** with stdio JSON-RPC transport
7. **HID server** for KVM devices (copied from existing project)
8. **Certificate generation script** for local setup
9. **KVM setup script** for provisioning new devices
10. **README** with documentation

The MCP server can be run with:
```bash
python -m glkvm_mcp.server
```

Or after `pip install -e .`:
```bash
glkvm-mcp
```
