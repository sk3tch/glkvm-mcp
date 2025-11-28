"""HTTPS client for communicating with KVM HID servers."""

import json
import ssl
import urllib.error
import urllib.request
from typing import Any

from .config import Config, Device


class KVMClientError(Exception):
    """Error communicating with KVM device."""

    pass


class KVMClient:
    """Client for communicating with a KVM HID server over mTLS."""

    def __init__(self, config: Config):
        self.config = config
        self._ssl_context: ssl.SSLContext | None = None

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

    def _request(self, device: Device, method: str, path: str, data: dict | None = None) -> Any:
        """Make an HTTP request to the KVM device."""
        url = f"{device.url}{path}"

        headers = {"Content-Type": "application/json"} if data else {}
        body = json.dumps(data).encode() if data else None

        request = urllib.request.Request(url, data=body, headers=headers, method=method)

        try:
            with urllib.request.urlopen(
                request, context=self._get_ssl_context(), timeout=30
            ) as response:
                content_type = response.headers.get("Content-Type", "")
                if "application/json" in content_type:
                    return json.loads(response.read().decode())
                else:
                    return response.read()
        except urllib.error.HTTPError as e:
            try:
                error_body = json.loads(e.read().decode())
                raise KVMClientError(f"HTTP {e.code}: {error_body.get('error', str(e))}") from e
            except json.JSONDecodeError:
                raise KVMClientError(f"HTTP {e.code}: {e.reason}") from e
        except urllib.error.URLError as e:
            raise KVMClientError(f"Connection failed: {e.reason}") from e
        except ssl.SSLError as e:
            raise KVMClientError(f"SSL error: {e}") from e

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
        x: int | None = None,
        y: int | None = None,
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

    def keyboard_press(self, device_id: str, key: str, modifiers: list[str] | None = None) -> dict:
        """Press a key or key combination."""
        device = self._get_device(device_id)
        data = {"key": key}
        if modifiers:
            data["modifiers"] = modifiers
        return self._request(device, "POST", "/keyboard/press", data)
