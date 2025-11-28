"""Tests for MCP tool definitions and handlers."""

import base64
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from glkvm_mcp.client import KVMClient
from glkvm_mcp.config import Config
from glkvm_mcp.ocr import OCRResult
from glkvm_mcp.tools import TOOLS, ToolHandler


class TestToolDefinitions:
    """Tests for TOOLS list."""

    def test_tools_count(self):
        """TOOLS contains 11 tool definitions."""
        assert len(TOOLS) == 11

    def test_tools_have_name(self):
        """All tools have a name."""
        for tool in TOOLS:
            assert "name" in tool
            assert isinstance(tool["name"], str)
            assert len(tool["name"]) > 0

    def test_tools_have_description(self):
        """All tools have a description."""
        for tool in TOOLS:
            assert "description" in tool
            assert isinstance(tool["description"], str)
            assert len(tool["description"]) > 0

    def test_tools_have_input_schema(self):
        """All tools have an inputSchema."""
        for tool in TOOLS:
            assert "inputSchema" in tool
            assert tool["inputSchema"]["type"] == "object"
            assert "properties" in tool["inputSchema"]
            assert "required" in tool["inputSchema"]

    def test_tool_names_unique(self):
        """All tool names are unique."""
        names = [t["name"] for t in TOOLS]
        assert len(names) == len(set(names))

    def test_expected_tools_present(self):
        """Expected tools are all present."""
        expected = [
            "kvm_list_devices",
            "kvm_add_device",
            "kvm_remove_device",
            "kvm_capture_screen",
            "kvm_screenshot_with_ocr",
            "kvm_find_and_click",
            "kvm_mouse_move",
            "kvm_mouse_click",
            "kvm_mouse_scroll",
            "kvm_keyboard_type",
            "kvm_keyboard_press",
        ]
        names = [t["name"] for t in TOOLS]
        for exp in expected:
            assert exp in names, f"Missing tool: {exp}"


class TestToolHandler:
    """Tests for ToolHandler class."""

    @pytest.fixture
    def mock_config(self, tmp_path):
        """Create mock config."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("""
devices:
  test-kvm:
    ip: 192.168.1.100
    port: 8443
    name: Test KVM
  other-kvm:
    ip: 192.168.1.101
""")
        return Config(config_file)

    @pytest.fixture
    def mock_client(self):
        """Create mock KVM client."""
        return MagicMock(spec=KVMClient)

    @pytest.fixture
    def handler(self, mock_config, mock_client):
        """Create ToolHandler with mocks."""
        return ToolHandler(mock_config, mock_client)

    def test_handler_unknown_tool(self, handler):
        """Unknown tool raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            handler.handle("unknown_tool", {})
        assert "Unknown tool" in str(exc_info.value)


class TestListDevices:
    """Tests for kvm_list_devices handler."""

    @pytest.fixture
    def handler(self, tmp_path):
        """Create handler with config."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("""
devices:
  kvm1:
    ip: 192.168.1.100
    name: First KVM
  kvm2:
    ip: 192.168.1.101
    port: 9000
""")
        config = Config(config_file)
        client = MagicMock(spec=KVMClient)
        return ToolHandler(config, client)

    def test_list_devices_multiple(self, handler):
        """list_devices returns all devices."""
        result = handler.handle("kvm_list_devices", {})
        assert "devices" in result
        assert len(result["devices"]) == 2

    def test_list_devices_fields(self, handler):
        """list_devices includes all device fields."""
        result = handler.handle("kvm_list_devices", {})
        device = next(d for d in result["devices"] if d["device_id"] == "kvm1")
        assert device["ip"] == "192.168.1.100"
        assert device["name"] == "First KVM"
        assert "port" in device
        assert "url" in device

    def test_list_devices_empty(self, tmp_path):
        """list_devices returns empty list when no devices."""
        config_file = tmp_path / "empty.yaml"
        config_file.write_text("")
        config = Config(config_file)
        handler = ToolHandler(config, MagicMock())
        result = handler.handle("kvm_list_devices", {})
        assert result["devices"] == []


class TestAddDevice:
    """Tests for kvm_add_device handler."""

    @pytest.fixture
    def handler(self, tmp_path):
        """Create handler with empty config."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("")
        config = Config(config_file)
        return ToolHandler(config, MagicMock())

    def test_add_device_minimal(self, handler):
        """add_device with minimal args."""
        result = handler.handle(
            "kvm_add_device",
            {
                "device_id": "new-kvm",
                "ip": "10.0.0.1",
            },
        )
        assert result["success"] is True
        assert result["device"]["device_id"] == "new-kvm"
        assert result["device"]["ip"] == "10.0.0.1"

    def test_add_device_full(self, handler):
        """add_device with all options."""
        result = handler.handle(
            "kvm_add_device",
            {
                "device_id": "new-kvm",
                "ip": "10.0.0.1",
                "port": 9000,
                "name": "New KVM Device",
            },
        )
        assert result["device"]["port"] == 9000
        assert result["device"]["name"] == "New KVM Device"


class TestRemoveDevice:
    """Tests for kvm_remove_device handler."""

    @pytest.fixture
    def handler(self, tmp_path):
        """Create handler with a device."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("""
devices:
  existing:
    ip: 192.168.1.100
""")
        config = Config(config_file)
        return ToolHandler(config, MagicMock())

    def test_remove_device_exists(self, handler):
        """remove_device returns success for existing device."""
        result = handler.handle("kvm_remove_device", {"device_id": "existing"})
        assert result["success"] is True
        assert "removed" in result["message"].lower()

    def test_remove_device_not_exists(self, handler):
        """remove_device returns failure for nonexistent device."""
        result = handler.handle("kvm_remove_device", {"device_id": "nonexistent"})
        assert result["success"] is False
        assert "not found" in result["message"].lower()


class TestCaptureScreen:
    """Tests for kvm_capture_screen handler."""

    @pytest.fixture
    def handler_with_mock_ocr(self, tmp_path):
        """Create handler with mocked screenshot processing."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("""
devices:
  test-kvm:
    ip: 192.168.1.100
""")
        config = Config(config_file)
        client = MagicMock(spec=KVMClient)
        client.capture_screenshot.return_value = b"fake h264"
        return ToolHandler(config, client)

    def test_capture_screen(self, handler_with_mock_ocr):
        """capture_screen returns base64 image."""
        # Create a test image
        img = Image.new("RGB", (100, 50), color="red")
        img_bytes = BytesIO()
        img.save(img_bytes, format="JPEG")
        jpeg_data = img_bytes.getvalue()
        # Create original image (larger)
        original_img = Image.new("RGB", (1920, 1080), color="red")

        with patch("glkvm_mcp.tools.process_screenshot") as mock_process:
            mock_process.return_value = (jpeg_data, img, original_img)
            result = handler_with_mock_ocr.handle("kvm_capture_screen", {"device_id": "test-kvm"})

        assert "image" in result
        assert result["width"] == 100
        assert result["height"] == 50
        assert result["original_width"] == 1920
        assert result["original_height"] == 1080
        assert result["format"] == "jpeg"
        # Verify base64 is valid
        decoded = base64.b64decode(result["image"])
        assert decoded == jpeg_data


class TestScreenshotWithOcr:
    """Tests for kvm_screenshot_with_ocr handler."""

    @pytest.fixture
    def handler(self, tmp_path):
        """Create handler."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("""
devices:
  test-kvm:
    ip: 192.168.1.100
""")
        config = Config(config_file)
        client = MagicMock(spec=KVMClient)
        client.capture_screenshot.return_value = b"fake h264"
        return ToolHandler(config, client)

    def test_screenshot_with_ocr(self, handler):
        """screenshot_with_ocr returns image, text, and boxes."""
        img = Image.new("RGB", (100, 50), color="white")
        img_bytes = BytesIO()
        img.save(img_bytes, format="JPEG")
        jpeg_data = img_bytes.getvalue()
        # Create original image (larger)
        original_img = Image.new("RGB", (1920, 1080), color="white")

        mock_ocr = OCRResult(
            text="Hello World",
            boxes=[
                {"word": "Hello", "x": 10, "y": 10, "width": 30, "height": 15, "confidence": 95}
            ],
        )

        with (
            patch("glkvm_mcp.tools.process_screenshot") as mock_process,
            patch("glkvm_mcp.tools.ocr_screenshot") as mock_ocr_fn,
        ):
            mock_process.return_value = (jpeg_data, img, original_img)
            mock_ocr_fn.return_value = (mock_ocr, original_img)

            result = handler.handle("kvm_screenshot_with_ocr", {"device_id": "test-kvm"})

        assert "image" in result
        assert result["text"] == "Hello World"
        assert len(result["boxes"]) == 1
        assert result["boxes"][0]["word"] == "Hello"


class TestFindAndClick:
    """Tests for kvm_find_and_click handler."""

    @pytest.fixture
    def handler(self, tmp_path):
        """Create handler."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("""
devices:
  test-kvm:
    ip: 192.168.1.100
""")
        config = Config(config_file)
        client = MagicMock(spec=KVMClient)
        client.capture_screenshot.return_value = b"fake h264"
        return ToolHandler(config, client)

    def test_find_and_click_single_match(self, handler):
        """Single match clicks and returns clicked=True."""
        img = Image.new("RGB", (1920, 1080), color="white")
        img_bytes = BytesIO()
        img.save(img_bytes, format="JPEG")

        mock_ocr = OCRResult(
            text="Submit",
            boxes=[
                {"word": "Submit", "x": 100, "y": 200, "width": 60, "height": 20, "confidence": 95}
            ],
        )

        with patch("glkvm_mcp.tools.ocr_screenshot") as mock_ocr_fn:
            mock_ocr_fn.return_value = (mock_ocr, img)

            result = handler.handle(
                "kvm_find_and_click",
                {
                    "device_id": "test-kvm",
                    "text": "Submit",
                },
            )

        assert result["clicked"] is True
        assert result["matches_found"] == 1
        assert "clicked_at" in result
        handler.client.mouse_click.assert_called_once()

    def test_find_and_click_no_click_option(self, handler):
        """click=False prevents clicking."""
        img = Image.new("RGB", (1920, 1080), color="white")
        img_bytes = BytesIO()
        img.save(img_bytes, format="JPEG")

        mock_ocr = OCRResult(
            text="Submit",
            boxes=[
                {"word": "Submit", "x": 100, "y": 200, "width": 60, "height": 20, "confidence": 95}
            ],
        )

        with patch("glkvm_mcp.tools.ocr_screenshot") as mock_ocr_fn:
            mock_ocr_fn.return_value = (mock_ocr, img)

            result = handler.handle(
                "kvm_find_and_click",
                {
                    "device_id": "test-kvm",
                    "text": "Submit",
                    "click": False,
                },
            )

        assert result["clicked"] is False
        handler.client.mouse_click.assert_not_called()

    def test_find_and_click_multiple_matches(self, handler):
        """Multiple matches don't click."""
        img = Image.new("RGB", (1920, 1080), color="white")
        img_bytes = BytesIO()
        img.save(img_bytes, format="JPEG")

        mock_ocr = OCRResult(
            text="OK OK",
            boxes=[
                {"word": "OK", "x": 100, "y": 200, "width": 30, "height": 20, "confidence": 95},
                {"word": "OK", "x": 200, "y": 200, "width": 30, "height": 20, "confidence": 90},
            ],
        )

        with patch("glkvm_mcp.tools.ocr_screenshot") as mock_ocr_fn:
            mock_ocr_fn.return_value = (mock_ocr, img)

            result = handler.handle(
                "kvm_find_and_click",
                {
                    "device_id": "test-kvm",
                    "text": "OK",
                },
            )

        assert result["clicked"] is False
        assert result["matches_found"] == 2
        assert "Multiple" in result["message"]
        handler.client.mouse_click.assert_not_called()

    def test_find_and_click_no_match(self, handler):
        """No matches returns message."""
        img = Image.new("RGB", (1920, 1080), color="white")
        img_bytes = BytesIO()
        img.save(img_bytes, format="JPEG")

        mock_ocr = OCRResult(text="", boxes=[])

        with patch("glkvm_mcp.tools.ocr_screenshot") as mock_ocr_fn:
            mock_ocr_fn.return_value = (mock_ocr, img)

            result = handler.handle(
                "kvm_find_and_click",
                {
                    "device_id": "test-kvm",
                    "text": "NotFound",
                },
            )

        assert result["clicked"] is False
        assert result["matches_found"] == 0
        assert "No matches" in result["message"]


class TestMouseOperations:
    """Tests for mouse operation handlers."""

    @pytest.fixture
    def handler(self, tmp_path):
        """Create handler."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("""
devices:
  test-kvm:
    ip: 192.168.1.100
""")
        config = Config(config_file)
        client = MagicMock(spec=KVMClient)
        client.mouse_move.return_value = {"success": True}
        client.mouse_click.return_value = {"success": True}
        client.mouse_scroll.return_value = {"success": True}
        return ToolHandler(config, client)

    def test_mouse_move(self, handler):
        """mouse_move calls client.mouse_move."""
        handler.handle(
            "kvm_mouse_move",
            {
                "device_id": "test-kvm",
                "x": 16383,
                "y": 16383,
            },
        )
        handler.client.mouse_move.assert_called_once_with("test-kvm", 16383, 16383)

    def test_mouse_click_defaults(self, handler):
        """mouse_click uses defaults."""
        handler.handle("kvm_mouse_click", {"device_id": "test-kvm"})
        handler.client.mouse_click.assert_called_once_with(
            device_id="test-kvm",
            button="left",
            double=False,
            x=None,
            y=None,
        )

    def test_mouse_click_options(self, handler):
        """mouse_click passes all options."""
        handler.handle(
            "kvm_mouse_click",
            {
                "device_id": "test-kvm",
                "button": "right",
                "double": True,
                "x": 1000,
                "y": 2000,
            },
        )
        handler.client.mouse_click.assert_called_once_with(
            device_id="test-kvm",
            button="right",
            double=True,
            x=1000,
            y=2000,
        )

    def test_mouse_scroll(self, handler):
        """mouse_scroll calls client.mouse_scroll."""
        handler.handle(
            "kvm_mouse_scroll",
            {
                "device_id": "test-kvm",
                "amount": 5,
            },
        )
        handler.client.mouse_scroll.assert_called_once_with("test-kvm", 5)


class TestKeyboardOperations:
    """Tests for keyboard operation handlers."""

    @pytest.fixture
    def handler(self, tmp_path):
        """Create handler."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("""
devices:
  test-kvm:
    ip: 192.168.1.100
""")
        config = Config(config_file)
        client = MagicMock(spec=KVMClient)
        client.keyboard_type.return_value = {"success": True}
        client.keyboard_press.return_value = {"success": True}
        return ToolHandler(config, client)

    def test_keyboard_type(self, handler):
        """keyboard_type calls client.keyboard_type."""
        handler.handle(
            "kvm_keyboard_type",
            {
                "device_id": "test-kvm",
                "text": "hello world",
            },
        )
        handler.client.keyboard_type.assert_called_once_with("test-kvm", "hello world")

    def test_keyboard_press_simple(self, handler):
        """keyboard_press with just key."""
        handler.handle(
            "kvm_keyboard_press",
            {
                "device_id": "test-kvm",
                "key": "Enter",
            },
        )
        handler.client.keyboard_press.assert_called_once_with(
            device_id="test-kvm",
            key="Enter",
            modifiers=None,
        )

    def test_keyboard_press_with_modifiers(self, handler):
        """keyboard_press with modifiers."""
        handler.handle(
            "kvm_keyboard_press",
            {
                "device_id": "test-kvm",
                "key": "c",
                "modifiers": ["ctrl"],
            },
        )
        handler.client.keyboard_press.assert_called_once_with(
            device_id="test-kvm",
            key="c",
            modifiers=["ctrl"],
        )
