"""Module-level functions for simple SDK usage.

This module provides a simple interface for controlling KVM devices without
explicitly creating KVM instances. A default device is used for all operations.

Example:
    import glkvm_mcp as glkvm

    glkvm.set_device("kvm-office")
    glkvm.click(100, 200)
    glkvm.type_text("hello world")
    shot = glkvm.screenshot()
"""

from .exceptions import KVMError
from .kvm import KVM
from .screenshot import Screenshot

# Global default KVM instance
_default_kvm: KVM | None = None


def set_device(
    device_id: str,
    *,
    port: int | None = None,
) -> KVM:
    """Set the default device for module-level functions.

    Args:
        device_id: Device ID from config file
        port: Optional port override

    Returns:
        The KVM instance that was created

    Raises:
        KVMDeviceNotFoundError: If device not found in config
    """
    global _default_kvm
    _default_kvm = KVM(device_id, port=port)
    return _default_kvm


def get_device() -> KVM | None:
    """Get the current default KVM device.

    Returns:
        The current default KVM instance, or None if not set
    """
    return _default_kvm


def _get_kvm() -> KVM:
    """Get the default KVM, raising if not set."""
    if _default_kvm is None:
        raise KVMError("No default device set. Call set_device() first or use KVM class directly.")
    return _default_kvm


def click(x: int, y: int, button: str = "left") -> None:
    """Click at coordinates using default device.

    Args:
        x: X coordinate
        y: Y coordinate
        button: Mouse button ("left", "right", or "middle")

    Raises:
        KVMError: If no default device set or click fails
    """
    _get_kvm().click(x, y, button)


def double_click(x: int, y: int, button: str = "left") -> None:
    """Double-click at coordinates using default device.

    Args:
        x: X coordinate
        y: Y coordinate
        button: Mouse button ("left", "right", or "middle")

    Raises:
        KVMError: If no default device set or double-click fails
    """
    _get_kvm().double_click(x, y, button)


def move(x: int, y: int) -> None:
    """Move mouse to coordinates using default device.

    Args:
        x: X coordinate
        y: Y coordinate

    Raises:
        KVMError: If no default device set or move fails
    """
    _get_kvm().move(x, y)


def scroll(x: int, y: int, delta_x: int = 0, delta_y: int = 0) -> None:
    """Scroll at coordinates using default device.

    Args:
        x: X coordinate
        y: Y coordinate
        delta_x: Horizontal scroll amount (positive = right)
        delta_y: Vertical scroll amount (positive = down)

    Raises:
        KVMError: If no default device set or scroll fails
    """
    _get_kvm().scroll(x, y, delta_x, delta_y)


def type_text(text: str) -> None:
    """Type text using default device.

    Args:
        text: Text to type

    Raises:
        KVMError: If no default device set or typing fails
    """
    _get_kvm().type_text(text)


def key(key: str, modifiers: list[str] | None = None) -> None:
    """Press a key using default device.

    Args:
        key: Key to press (e.g., "Enter", "Tab", "a", "F1")
        modifiers: List of modifiers (e.g., ["ctrl"], ["ctrl", "shift"])

    Raises:
        KVMError: If no default device set or key press fails
    """
    _get_kvm().key(key, modifiers)


def screenshot(format: str = "png") -> Screenshot:
    """Capture a screenshot using default device.

    Args:
        format: Image format ("png" or "jpeg")

    Returns:
        Screenshot object with image data

    Raises:
        KVMError: If no default device set or screenshot fails
    """
    return _get_kvm().screenshot(format)
