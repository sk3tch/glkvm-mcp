"""Tests for KVM class."""

from unittest.mock import MagicMock

import pytest

from glkvm_mcp.sdk.exceptions import (
    KVMConnectionError,
    KVMDeviceNotFoundError,
    KVMError,
)
from glkvm_mcp.sdk.kvm import KVM
from glkvm_mcp.sdk.screenshot import Screenshot


@pytest.fixture
def mock_config_with_device(tmp_path):
    """Create a temporary config file with a test device."""
    config_dir = tmp_path / ".config" / "glkvm-mcp"
    config_dir.mkdir(parents=True)

    config_file = config_dir / "config.yaml"
    config_file.write_text("""
devices:
  test-device:
    ip: 192.168.1.100
    port: 8443
    name: Test Device
  other-device:
    ip: 192.168.1.101
""")

    # Create dummy cert files
    certs_dir = config_dir / "certs"
    certs_dir.mkdir()
    (certs_dir / "ca.crt").write_text("fake ca cert")
    (certs_dir / "client.crt").write_text("fake client cert")
    (certs_dir / "client.key").write_text("fake client key")

    return config_file


class TestKVMInit:
    """Test KVM initialization."""

    def test_init_with_device_id(self, mock_config_with_device):
        """KVM can be initialized with device_id from config."""
        kvm = KVM("test-device", config_path=mock_config_with_device)
        assert kvm.device_id == "test-device"
        assert kvm.host == "192.168.1.100"
        assert kvm.port == 8443

    def test_init_with_host(self, mock_config_with_device):
        """KVM can be initialized with explicit host."""
        kvm = KVM(host="10.0.0.1", port=9000, config_path=mock_config_with_device)
        assert kvm.host == "10.0.0.1"
        assert kvm.port == 9000

    def test_init_with_port_override(self, mock_config_with_device):
        """Port can be overridden for config device."""
        kvm = KVM("test-device", port=9999, config_path=mock_config_with_device)
        assert kvm.device_id == "test-device"
        assert kvm.host == "192.168.1.100"
        assert kvm.port == 9999

    def test_init_device_not_found(self, mock_config_with_device):
        """KVMDeviceNotFoundError raised for unknown device."""
        with pytest.raises(KVMDeviceNotFoundError) as exc_info:
            KVM("nonexistent", config_path=mock_config_with_device)
        assert "nonexistent" in str(exc_info.value)
        assert "test-device" in str(exc_info.value)  # Shows available

    def test_init_requires_device_or_host(self, mock_config_with_device):
        """ValueError raised if neither device_id nor host provided."""
        with pytest.raises(ValueError) as exc_info:
            KVM(config_path=mock_config_with_device)
        assert "device_id or host" in str(exc_info.value)

    def test_repr_with_device_id(self, mock_config_with_device):
        """repr shows device_id when initialized from config."""
        kvm = KVM("test-device", config_path=mock_config_with_device)
        r = repr(kvm)
        assert "test-device" in r
        assert "192.168.1.100" in r

    def test_repr_with_host(self, mock_config_with_device):
        """repr shows host/port when initialized directly."""
        kvm = KVM(host="10.0.0.1", port=8443, config_path=mock_config_with_device)
        r = repr(kvm)
        assert "10.0.0.1" in r
        assert "8443" in r


class TestKVMOperations:
    """Test KVM operations with mocked client."""

    @pytest.fixture
    def kvm_with_mock_client(self, mock_config_with_device):
        """Create KVM with mocked underlying client."""
        kvm = KVM("test-device", config_path=mock_config_with_device)
        kvm._client = MagicMock()
        return kvm

    def test_click(self, kvm_with_mock_client):
        """click() calls client.mouse_click."""
        kvm_with_mock_client.click(100, 200, button="right")
        kvm_with_mock_client._client.mouse_click.assert_called_once_with(
            "test-device", button="right", x=100, y=200
        )

    def test_double_click(self, kvm_with_mock_client):
        """double_click() calls client.mouse_click with double=True."""
        kvm_with_mock_client.double_click(100, 200)
        kvm_with_mock_client._client.mouse_click.assert_called_once_with(
            "test-device", button="left", double=True, x=100, y=200
        )

    def test_move(self, kvm_with_mock_client):
        """move() calls client.mouse_move."""
        kvm_with_mock_client.move(300, 400)
        kvm_with_mock_client._client.mouse_move.assert_called_once_with("test-device", 300, 400)

    def test_scroll(self, kvm_with_mock_client):
        """scroll() moves then scrolls."""
        kvm_with_mock_client.scroll(100, 200, delta_y=5)
        kvm_with_mock_client._client.mouse_move.assert_called_once_with("test-device", 100, 200)
        # delta_y=5 means scroll down, API uses negative for down
        kvm_with_mock_client._client.mouse_scroll.assert_called_once_with("test-device", -5)

    def test_scroll_at_origin_skips_move(self, kvm_with_mock_client):
        """scroll() at (0,0) skips the move."""
        kvm_with_mock_client.scroll(0, 0, delta_y=3)
        kvm_with_mock_client._client.mouse_move.assert_not_called()
        kvm_with_mock_client._client.mouse_scroll.assert_called_once()

    def test_type_text(self, kvm_with_mock_client):
        """type_text() calls client.keyboard_type."""
        kvm_with_mock_client.type_text("hello world")
        kvm_with_mock_client._client.keyboard_type.assert_called_once_with(
            "test-device", "hello world"
        )

    def test_key(self, kvm_with_mock_client):
        """key() calls client.keyboard_press."""
        kvm_with_mock_client.key("Enter")
        kvm_with_mock_client._client.keyboard_press.assert_called_once_with(
            "test-device", "Enter", None
        )

    def test_key_with_modifiers(self, kvm_with_mock_client):
        """key() passes modifiers."""
        kvm_with_mock_client.key("c", modifiers=["ctrl"])
        kvm_with_mock_client._client.keyboard_press.assert_called_once_with(
            "test-device", "c", ["ctrl"]
        )

    def test_screenshot(self, kvm_with_mock_client):
        """screenshot() returns Screenshot object."""
        kvm_with_mock_client._client.capture_screenshot.return_value = b"png data"
        shot = kvm_with_mock_client.screenshot()
        assert isinstance(shot, Screenshot)
        assert shot.data == b"png data"
        assert shot.format == "png"

    def test_screenshot_with_format(self, kvm_with_mock_client):
        """screenshot() accepts format parameter."""
        kvm_with_mock_client._client.capture_screenshot.return_value = b"jpeg data"
        shot = kvm_with_mock_client.screenshot(format="jpeg")
        assert shot.format == "jpeg"

    def test_health_check(self, kvm_with_mock_client):
        """health_check() returns status dict."""
        kvm_with_mock_client._client.health_check.return_value = {"status": "ok"}
        result = kvm_with_mock_client.health_check()
        assert result == {"status": "ok"}


class TestKVMErrorHandling:
    """Test KVM error handling."""

    @pytest.fixture
    def kvm_with_failing_client(self, mock_config_with_device):
        """Create KVM with client that raises errors."""
        kvm = KVM("test-device", config_path=mock_config_with_device)
        kvm._client = MagicMock()
        return kvm

    def test_click_error_wrapped(self, kvm_with_failing_client):
        """Client errors are wrapped in KVMError."""
        from glkvm_mcp.client import KVMClientError

        kvm_with_failing_client._client.mouse_click.side_effect = KVMClientError("fail")

        with pytest.raises(KVMError) as exc_info:
            kvm_with_failing_client.click(0, 0)
        assert "Click failed" in str(exc_info.value)

    def test_connection_error_detected(self, kvm_with_failing_client):
        """Connection errors become KVMConnectionError."""
        from glkvm_mcp.client import KVMClientError

        kvm_with_failing_client._client.mouse_click.side_effect = KVMClientError(
            "Connection refused"
        )

        with pytest.raises(KVMConnectionError):
            kvm_with_failing_client.click(0, 0)

    def test_ssl_error_detected(self, kvm_with_failing_client):
        """SSL errors become KVMConnectionError."""
        from glkvm_mcp.client import KVMClientError

        kvm_with_failing_client._client.mouse_click.side_effect = KVMClientError(
            "SSL certificate verify failed"
        )

        with pytest.raises(KVMConnectionError):
            kvm_with_failing_client.click(0, 0)
