"""Tests for KVM HTTP client."""

import json
import ssl
import urllib.error
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest

from glkvm_mcp.client import KVMClient, KVMClientError
from glkvm_mcp.config import Config


@pytest.fixture
def mock_config(tmp_path):
    """Create a Config with a test device."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
devices:
  test-kvm:
    ip: 192.168.1.100
    port: 8443
""")
    # Create dummy cert files
    certs_dir = tmp_path / "certs"
    certs_dir.mkdir()
    (certs_dir / "ca.crt").write_text("fake ca")
    (certs_dir / "client.crt").write_text("fake client cert")
    (certs_dir / "client.key").write_text("fake client key")

    config_file_with_certs = tmp_path / "config.yaml"
    config_file_with_certs.write_text(f"""
certs_dir: {certs_dir}
devices:
  test-kvm:
    ip: 192.168.1.100
    port: 8443
""")
    return Config(config_file_with_certs)


class TestKVMClientInit:
    """Tests for KVMClient initialization."""

    def test_client_init(self, mock_config):
        """Client initializes with config."""
        client = KVMClient(mock_config)
        assert client.config is mock_config
        assert client._ssl_context is None


class TestKVMClientSSL:
    """Tests for SSL context handling."""

    def test_ssl_context_creation(self, mock_config):
        """_get_ssl_context creates SSL context."""
        client = KVMClient(mock_config)

        with patch("ssl.create_default_context") as mock_create:
            mock_ctx = MagicMock()
            mock_create.return_value = mock_ctx

            client._get_ssl_context()

            mock_create.assert_called_once_with(
                purpose=ssl.Purpose.SERVER_AUTH,
                cafile=str(mock_config.ca_cert_path),
            )
            mock_ctx.load_cert_chain.assert_called_once_with(
                certfile=str(mock_config.client_cert_path),
                keyfile=str(mock_config.client_key_path),
            )

    def test_ssl_context_caching(self, mock_config):
        """_get_ssl_context caches and reuses context."""
        client = KVMClient(mock_config)

        with patch("ssl.create_default_context") as mock_create:
            mock_ctx = MagicMock()
            mock_create.return_value = mock_ctx

            ctx1 = client._get_ssl_context()
            ctx2 = client._get_ssl_context()

            # Should only create once
            assert mock_create.call_count == 1
            assert ctx1 is ctx2


class TestKVMClientGetDevice:
    """Tests for device lookup."""

    def test_get_device_found(self, mock_config):
        """_get_device returns device when found."""
        client = KVMClient(mock_config)
        device = client._get_device("test-kvm")
        assert device.ip == "192.168.1.100"

    def test_get_device_not_found(self, mock_config):
        """_get_device raises KVMClientError when not found."""
        client = KVMClient(mock_config)
        with pytest.raises(KVMClientError) as exc_info:
            client._get_device("nonexistent")
        assert "Device not found" in str(exc_info.value)
        assert "nonexistent" in str(exc_info.value)


class TestKVMClientRequests:
    """Tests for HTTP request handling."""

    @pytest.fixture
    def client_with_mocked_request(self, mock_config):
        """Create client with mocked _request method."""
        client = KVMClient(mock_config)
        client._request = MagicMock()
        return client

    def test_health_check(self, client_with_mocked_request):
        """health_check calls GET /health."""
        client_with_mocked_request._request.return_value = {"status": "ok"}
        result = client_with_mocked_request.health_check("test-kvm")

        assert result == {"status": "ok"}
        call_args = client_with_mocked_request._request.call_args
        assert call_args[0][1] == "GET"
        assert call_args[0][2] == "/health"

    def test_capture_screenshot(self, client_with_mocked_request):
        """capture_screenshot calls GET /screenshot."""
        client_with_mocked_request._request.return_value = b"screenshot data"
        result = client_with_mocked_request.capture_screenshot("test-kvm")

        assert result == b"screenshot data"
        call_args = client_with_mocked_request._request.call_args
        assert call_args[0][1] == "GET"
        assert call_args[0][2] == "/screenshot"

    def test_mouse_move(self, client_with_mocked_request):
        """mouse_move calls POST /mouse/move with coordinates."""
        client_with_mocked_request._request.return_value = {"success": True}
        result = client_with_mocked_request.mouse_move("test-kvm", 1000, 2000)

        assert result == {"success": True}
        call_args = client_with_mocked_request._request.call_args
        assert call_args[0][1] == "POST"
        assert call_args[0][2] == "/mouse/move"
        assert call_args[0][3] == {"x": 1000, "y": 2000}

    def test_mouse_click_defaults(self, client_with_mocked_request):
        """mouse_click defaults to left button, no double."""
        client_with_mocked_request._request.return_value = {"success": True}
        client_with_mocked_request.mouse_click("test-kvm")

        call_args = client_with_mocked_request._request.call_args
        assert call_args[0][2] == "/mouse/click"
        data = call_args[0][3]
        assert data["button"] == "left"
        assert data["double"] is False
        assert "x" not in data
        assert "y" not in data

    def test_mouse_click_with_options(self, client_with_mocked_request):
        """mouse_click accepts button, double, coordinates."""
        client_with_mocked_request._request.return_value = {"success": True}
        client_with_mocked_request.mouse_click(
            "test-kvm", button="right", double=True, x=100, y=200
        )

        call_args = client_with_mocked_request._request.call_args
        data = call_args[0][3]
        assert data["button"] == "right"
        assert data["double"] is True
        assert data["x"] == 100
        assert data["y"] == 200

    def test_mouse_scroll(self, client_with_mocked_request):
        """mouse_scroll calls POST /mouse/scroll."""
        client_with_mocked_request._request.return_value = {"success": True}
        client_with_mocked_request.mouse_scroll("test-kvm", 5)

        call_args = client_with_mocked_request._request.call_args
        assert call_args[0][2] == "/mouse/scroll"
        assert call_args[0][3] == {"amount": 5}

    def test_keyboard_type(self, client_with_mocked_request):
        """keyboard_type calls POST /keyboard/type."""
        client_with_mocked_request._request.return_value = {"success": True}
        client_with_mocked_request.keyboard_type("test-kvm", "hello world")

        call_args = client_with_mocked_request._request.call_args
        assert call_args[0][2] == "/keyboard/type"
        assert call_args[0][3] == {"text": "hello world"}

    def test_keyboard_press_simple(self, client_with_mocked_request):
        """keyboard_press calls POST /keyboard/press with key."""
        client_with_mocked_request._request.return_value = {"success": True}
        client_with_mocked_request.keyboard_press("test-kvm", "Enter")

        call_args = client_with_mocked_request._request.call_args
        assert call_args[0][2] == "/keyboard/press"
        data = call_args[0][3]
        assert data["key"] == "Enter"
        assert "modifiers" not in data

    def test_keyboard_press_with_modifiers(self, client_with_mocked_request):
        """keyboard_press includes modifiers list."""
        client_with_mocked_request._request.return_value = {"success": True}
        client_with_mocked_request.keyboard_press("test-kvm", "c", ["ctrl"])

        call_args = client_with_mocked_request._request.call_args
        data = call_args[0][3]
        assert data["key"] == "c"
        assert data["modifiers"] == ["ctrl"]


class TestKVMClientRequestErrors:
    """Tests for HTTP error handling."""

    @pytest.fixture
    def client(self, mock_config):
        """Create client with mocked SSL."""
        client = KVMClient(mock_config)
        # Mock SSL context to avoid needing real certs
        client._ssl_context = MagicMock()
        return client

    def test_request_http_error_json_body(self, client):
        """HTTP errors with JSON body parse error message."""
        error_response = BytesIO(json.dumps({"error": "Bad request"}).encode())
        http_error = urllib.error.HTTPError("https://test", 400, "Bad Request", {}, error_response)

        with patch("urllib.request.urlopen", side_effect=http_error):
            with pytest.raises(KVMClientError) as exc_info:
                client.health_check("test-kvm")
            assert "HTTP 400" in str(exc_info.value)
            assert "Bad request" in str(exc_info.value)

    def test_request_http_error_plain_body(self, client):
        """HTTP errors without JSON fall back to reason."""
        error_response = BytesIO(b"not json")
        http_error = urllib.error.HTTPError(
            "https://test", 500, "Internal Server Error", {}, error_response
        )

        with patch("urllib.request.urlopen", side_effect=http_error):
            with pytest.raises(KVMClientError) as exc_info:
                client.health_check("test-kvm")
            assert "HTTP 500" in str(exc_info.value)
            assert "Internal Server Error" in str(exc_info.value)

    def test_request_url_error(self, client):
        """URLError raises KVMClientError."""
        url_error = urllib.error.URLError("Connection refused")

        with patch("urllib.request.urlopen", side_effect=url_error):
            with pytest.raises(KVMClientError) as exc_info:
                client.health_check("test-kvm")
            assert "Connection failed" in str(exc_info.value)

    def test_request_ssl_error(self, client):
        """SSLError raises KVMClientError."""
        ssl_error = ssl.SSLError("certificate verify failed")

        with patch("urllib.request.urlopen", side_effect=ssl_error):
            with pytest.raises(KVMClientError) as exc_info:
                client.health_check("test-kvm")
            assert "SSL error" in str(exc_info.value)


class TestKVMClientRequestSuccess:
    """Tests for successful HTTP responses."""

    @pytest.fixture
    def client(self, mock_config):
        """Create client with mocked SSL."""
        client = KVMClient(mock_config)
        client._ssl_context = MagicMock()
        return client

    def test_request_json_response(self, client):
        """JSON responses are parsed."""
        mock_response = MagicMock()
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.read.return_value = json.dumps({"status": "ok"}).encode()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response):
            result = client.health_check("test-kvm")
            assert result == {"status": "ok"}

    def test_request_binary_response(self, client):
        """Binary responses are returned as bytes."""
        mock_response = MagicMock()
        mock_response.headers = {"Content-Type": "application/octet-stream"}
        mock_response.read.return_value = b"binary data"
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response):
            result = client.capture_screenshot("test-kvm")
            assert result == b"binary data"
