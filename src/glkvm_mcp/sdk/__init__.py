"""GLKVM SDK - Python SDK for controlling KVM devices."""

from .exceptions import KVMConnectionError, KVMDeviceNotFoundError, KVMError
from .kvm import KVM
from .module import (
    click,
    double_click,
    get_device,
    key,
    move,
    screenshot,
    scroll,
    set_device,
    type_text,
)
from .screenshot import Screenshot

__all__ = [
    "KVM",
    "KVMConnectionError",
    "KVMDeviceNotFoundError",
    "KVMError",
    "Screenshot",
    "click",
    "double_click",
    "get_device",
    "key",
    "move",
    "screenshot",
    "scroll",
    "set_device",
    "type_text",
]
