"""Tests for module-level SDK functions."""

from unittest.mock import MagicMock, patch

import pytest

from glkvm_mcp.sdk import module
from glkvm_mcp.sdk.exceptions import KVMError


@pytest.fixture(autouse=True)
def reset_default_device():
    """Reset the default device before and after each test."""
    module._default_kvm = None
    yield
    module._default_kvm = None


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
""")

    certs_dir = config_dir / "certs"
    certs_dir.mkdir()
    (certs_dir / "ca.crt").write_text("fake")
    (certs_dir / "client.crt").write_text("fake")
    (certs_dir / "client.key").write_text("fake")

    return config_file


class TestSetDevice:
    """Test set_device function."""

    def test_set_device_creates_kvm(self, mock_config_with_device):
        """set_device creates and stores a KVM instance."""
        with patch.object(module, "KVM") as mock_kvm_class:
            mock_kvm = MagicMock()
            mock_kvm_class.return_value = mock_kvm

            result = module.set_device("test-device", port=9000)

            mock_kvm_class.assert_called_once_with("test-device", port=9000)
            assert result is mock_kvm
            assert module._default_kvm is mock_kvm

    def test_set_device_replaces_existing(self, mock_config_with_device):
        """set_device replaces any existing default."""
        with patch.object(module, "KVM") as mock_kvm_class:
            mock_kvm1 = MagicMock()
            mock_kvm2 = MagicMock()
            mock_kvm_class.side_effect = [mock_kvm1, mock_kvm2]

            module.set_device("device1")
            assert module._default_kvm is mock_kvm1

            module.set_device("device2")
            assert module._default_kvm is mock_kvm2


class TestGetDevice:
    """Test get_device function."""

    def test_get_device_returns_none_initially(self):
        """get_device returns None when no device set."""
        assert module.get_device() is None

    def test_get_device_returns_current(self):
        """get_device returns the current default KVM."""
        mock_kvm = MagicMock()
        module._default_kvm = mock_kvm
        assert module.get_device() is mock_kvm


class TestModuleFunctionsWithoutDevice:
    """Test module functions raise when no device set."""

    def test_click_raises_without_device(self):
        """click raises KVMError when no default device."""
        with pytest.raises(KVMError) as exc_info:
            module.click(0, 0)
        assert "No default device" in str(exc_info.value)
        assert "set_device()" in str(exc_info.value)

    def test_double_click_raises_without_device(self):
        """double_click raises KVMError when no default device."""
        with pytest.raises(KVMError):
            module.double_click(0, 0)

    def test_move_raises_without_device(self):
        """move raises KVMError when no default device."""
        with pytest.raises(KVMError):
            module.move(0, 0)

    def test_scroll_raises_without_device(self):
        """scroll raises KVMError when no default device."""
        with pytest.raises(KVMError):
            module.scroll(0, 0)

    def test_type_text_raises_without_device(self):
        """type_text raises KVMError when no default device."""
        with pytest.raises(KVMError):
            module.type_text("hello")

    def test_key_raises_without_device(self):
        """key raises KVMError when no default device."""
        with pytest.raises(KVMError):
            module.key("Enter")

    def test_screenshot_raises_without_device(self):
        """screenshot raises KVMError when no default device."""
        with pytest.raises(KVMError):
            module.screenshot()


class TestModuleFunctionsWithDevice:
    """Test module functions delegate to default KVM."""

    @pytest.fixture
    def mock_default_kvm(self):
        """Set up a mock default KVM."""
        mock_kvm = MagicMock()
        module._default_kvm = mock_kvm
        return mock_kvm

    def test_click_delegates(self, mock_default_kvm):
        """click delegates to default KVM."""
        module.click(100, 200, button="right")
        mock_default_kvm.click.assert_called_once_with(100, 200, "right")

    def test_double_click_delegates(self, mock_default_kvm):
        """double_click delegates to default KVM."""
        module.double_click(100, 200, button="middle")
        mock_default_kvm.double_click.assert_called_once_with(100, 200, "middle")

    def test_move_delegates(self, mock_default_kvm):
        """move delegates to default KVM."""
        module.move(300, 400)
        mock_default_kvm.move.assert_called_once_with(300, 400)

    def test_scroll_delegates(self, mock_default_kvm):
        """scroll delegates to default KVM."""
        module.scroll(100, 200, delta_x=1, delta_y=2)
        mock_default_kvm.scroll.assert_called_once_with(100, 200, 1, 2)

    def test_type_text_delegates(self, mock_default_kvm):
        """type_text delegates to default KVM."""
        module.type_text("hello world")
        mock_default_kvm.type_text.assert_called_once_with("hello world")

    def test_key_delegates(self, mock_default_kvm):
        """key delegates to default KVM."""
        module.key("Enter", modifiers=["ctrl"])
        mock_default_kvm.key.assert_called_once_with("Enter", ["ctrl"])

    def test_screenshot_delegates(self, mock_default_kvm):
        """screenshot delegates to default KVM."""
        mock_shot = MagicMock()
        mock_default_kvm.screenshot.return_value = mock_shot

        result = module.screenshot(format="jpeg")

        mock_default_kvm.screenshot.assert_called_once_with("jpeg")
        assert result is mock_shot
