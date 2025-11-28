"""Tests for SDK exceptions."""

import pytest

from glkvm_mcp.sdk.exceptions import (
    KVMConnectionError,
    KVMDeviceNotFoundError,
    KVMError,
)


class TestExceptionHierarchy:
    """Test exception class hierarchy."""

    def test_kvm_error_is_exception(self):
        """KVMError inherits from Exception."""
        assert issubclass(KVMError, Exception)

    def test_connection_error_is_kvm_error(self):
        """KVMConnectionError inherits from KVMError."""
        assert issubclass(KVMConnectionError, KVMError)

    def test_device_not_found_is_kvm_error(self):
        """KVMDeviceNotFoundError inherits from KVMError."""
        assert issubclass(KVMDeviceNotFoundError, KVMError)


class TestExceptionUsage:
    """Test exception instantiation and catching."""

    def test_kvm_error_with_message(self):
        """KVMError can be raised with message."""
        with pytest.raises(KVMError) as exc_info:
            raise KVMError("something went wrong")
        assert "something went wrong" in str(exc_info.value)

    def test_connection_error_caught_as_kvm_error(self):
        """KVMConnectionError can be caught as KVMError."""
        with pytest.raises(KVMError):
            raise KVMConnectionError("connection failed")

    def test_device_not_found_caught_as_kvm_error(self):
        """KVMDeviceNotFoundError can be caught as KVMError."""
        with pytest.raises(KVMError):
            raise KVMDeviceNotFoundError("device missing")

    def test_specific_exceptions_distinguishable(self):
        """Specific exceptions can be caught separately."""
        # Can catch connection error specifically
        try:
            raise KVMConnectionError("conn error")
        except KVMDeviceNotFoundError:
            pytest.fail("Should not catch as DeviceNotFound")
        except KVMConnectionError as e:
            assert "conn error" in str(e)

        # Can catch device not found specifically
        try:
            raise KVMDeviceNotFoundError("no device")
        except KVMConnectionError:
            pytest.fail("Should not catch as ConnectionError")
        except KVMDeviceNotFoundError as e:
            assert "no device" in str(e)
