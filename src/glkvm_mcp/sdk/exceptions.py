"""SDK exceptions."""


class KVMError(Exception):
    """Base exception for KVM errors."""

    pass


class KVMConnectionError(KVMError):
    """Raised when connection to KVM device fails."""

    pass


class KVMDeviceNotFoundError(KVMError):
    """Raised when a device is not found in configuration."""

    pass
