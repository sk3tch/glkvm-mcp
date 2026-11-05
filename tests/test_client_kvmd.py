"""Tests for the PiKVM/KVMD backend of the KVM client."""

import pytest

from glkvm_mcp.client import KVMClient
from glkvm_mcp.config import Config


@pytest.fixture
def kvmd_client(tmp_path):
    """Client with a single KVMD device."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
devices:
  pi:
    ip: 192.168.1.50
    port: 80
    kind: kvmd
    username: admin
    password: admin
""")
    return KVMClient(Config(config_file))


def test_device_defaults_to_http_for_kvmd(kvmd_client):
    device = kvmd_client._get_device("pi")
    assert device.url == "http://192.168.1.50:80"
    assert device.kind == "kvmd"


def test_screenshot_uses_kvmd_snapshot(kvmd_client, monkeypatch):
    calls = {}

    def fake_request(device, method, path, data=None):
        calls["method"] = method
        calls["path"] = path
        calls["data"] = data
        return b"jpeg"

    monkeypatch.setattr(kvmd_client, "_request", fake_request)
    assert kvmd_client.capture_screenshot("pi") == b"jpeg"
    assert calls["method"] == "GET"
    assert calls["path"] == "/api/streamer/snapshot"


def test_health_uses_kvmd_state(kvmd_client, monkeypatch):
    calls = {}
    monkeypatch.setattr(
        kvmd_client, "_request", lambda d, m, p, data=None: calls.update(path=p)
    )
    kvmd_client.health_check("pi")
    assert calls["path"] == "/api/streamer/state"


def test_key_press_uses_kvmd_send_key(kvmd_client, monkeypatch):
    calls = {}
    monkeypatch.setattr(
        kvmd_client,
        "_request",
        lambda d, m, p, data=None: calls.update(path=p, data=data),
    )
    kvmd_client.keyboard_press("pi", "c", modifiers=["ctrl"])
    assert calls["path"] == "/api/hid/events/send_key"
    assert calls["data"] == {"key": "ctrl+c"}


def test_type_uses_kvmd_send_text(kvmd_client, monkeypatch):
    calls = {}
    monkeypatch.setattr(
        kvmd_client,
        "_request",
        lambda d, m, p, data=None: calls.update(path=p, data=data),
    )
    kvmd_client.keyboard_type("pi", "hello")
    assert calls["path"] == "/api/hid/events/send_text"
    assert calls["data"] == {"text": "hello"}


def test_mouse_move_is_relative_for_kvmd(kvmd_client, monkeypatch):
    calls = []
    monkeypatch.setattr(
        kvmd_client,
        "_request",
        lambda d, m, p, data=None: calls.append((p, data)),
    )
    # First move is relative to the assumed centre (16383, 16383).
    kvmd_client.mouse_move("pi", 16383 + 100, 16383)
    assert calls[0][0] == "/api/hid/events/send_mouse"
    assert calls[0][1] == {"move": {"dx": 100, "dy": 0}}
    # Second move is relative to the previous position.
    kvmd_client.mouse_move("pi", 16383 + 150, 16383 + 50)
    assert calls[1][1] == {"move": {"dx": 50, "dy": 50}}


def test_mouse_click_and_scroll_use_kvmd_events(kvmd_client, monkeypatch):
    calls = []
    monkeypatch.setattr(
        kvmd_client,
        "_request",
        lambda d, m, p, data=None: calls.append((p, data)),
    )
    kvmd_client.mouse_click("pi", button="right")
    assert calls[0] == ("/api/hid/events/send_mouse", {"click": {"button": "right"}})
    kvmd_client.mouse_scroll("pi", -3)
    assert calls[1] == ("/api/hid/events/send_mouse", {"wheel": {"delta": -3}})


def test_kvmd_auth_headers(kvmd_client):
    device = kvmd_client._get_device("pi")
    headers = kvmd_client._auth_headers(device)
    assert headers["X-KVMD-User"] == "admin"
    assert headers["X-KVMD-Passwd"] == "admin"


def test_hid_server_keeps_mutual_tls(kvmd_client, tmp_path):
    config_file = tmp_path / "hid.yaml"
    config_file.write_text("""
devices:
  gl:
    ip: 192.168.1.60
    port: 8443
""")
    client = KVMClient(Config(config_file))
    device = client._get_device("gl")
    assert device.kind == "hid-server"
    assert device.url == "https://192.168.1.60:8443"
    assert client._auth_headers(device) == {}
