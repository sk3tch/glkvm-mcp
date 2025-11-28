"""KVM class for controlling KVM devices."""

from pathlib import Path

from ..client import KVMClient, KVMClientError
from ..config import Config, Device
from .exceptions import KVMConnectionError, KVMDeviceNotFoundError, KVMError
from .screenshot import Screenshot


class KVM:
    """A KVM device controller.

    Provides methods to control a KVM device: mouse, keyboard, and screenshots.

    Can be initialized with either a device ID (from config) or explicit connection
    parameters.

    Examples:
        # From config file
        kvm = KVM("kvm-office")

        # Explicit connection
        kvm = KVM(host="192.168.1.100", port=8443)

        # Config with overrides
        kvm = KVM("kvm-office", port=9443)
    """

    def __init__(
        self,
        device_id: str | None = None,
        *,
        host: str | None = None,
        port: int | None = None,
        config_path: str | Path | None = None,
    ):
        """Initialize KVM controller.

        Args:
            device_id: Device ID from config file. If provided, connection details
                      are loaded from config.
            host: KVM device hostname or IP. Required if device_id not provided.
            port: KVM device port. Defaults to config default or 8443.
            config_path: Path to config file. Defaults to ~/.config/glkvm-mcp/config.yaml.

        Raises:
            KVMDeviceNotFoundError: If device_id is provided but not found in config.
            ValueError: If neither device_id nor host is provided.
        """
        # Load config
        config_path_obj = Path(config_path) if config_path else None
        self._config = Config(config_path_obj)

        # Resolve device
        if device_id is not None:
            device = self._config.get_device(device_id)
            if device is None:
                available = [d.device_id for d in self._config.list_devices()]
                raise KVMDeviceNotFoundError(
                    f"Device '{device_id}' not found in config. Available devices: {available}"
                )
            self._device_id = device_id
            # Apply port override if provided
            if port is not None and port != device.port:
                self._device = Device(
                    device_id=device.device_id,
                    ip=device.ip,
                    port=port,
                    name=device.name,
                )
                # Update in config for client to use
                self._config.devices[device_id] = self._device
            else:
                self._device = device
        elif host is not None:
            # Create ad-hoc device
            self._device_id = f"_adhoc_{host}"
            self._device = Device(
                device_id=self._device_id,
                ip=host,
                port=port or self._config.default_port,
            )
            # Add to config for the client to find
            self._config.devices[self._device_id] = self._device
        else:
            raise ValueError("Either device_id or host must be provided")

        # Create the underlying client
        self._client = KVMClient(self._config)

    @property
    def device_id(self) -> str:
        """Device ID."""
        return self._device_id

    @property
    def host(self) -> str:
        """KVM device host."""
        return self._device.ip

    @property
    def port(self) -> int:
        """KVM device port."""
        return self._device.port

    def _wrap_error(self, e: Exception, operation: str) -> KVMError:
        """Wrap an exception in an appropriate KVMError."""
        msg = str(e).lower()
        if "connection" in msg or "ssl" in msg:
            return KVMConnectionError(f"{operation} failed: {e}")
        return KVMError(f"{operation} failed: {e}")

    def click(
        self,
        x: int,
        y: int,
        button: str = "left",
    ) -> None:
        """Click at coordinates.

        Args:
            x: X coordinate
            y: Y coordinate
            button: Mouse button ("left", "right", or "middle")

        Raises:
            KVMError: If the click fails
        """
        try:
            self._client.mouse_click(self._device_id, button=button, x=x, y=y)
        except KVMClientError as e:
            raise self._wrap_error(e, "Click") from e

    def double_click(self, x: int, y: int, button: str = "left") -> None:
        """Double-click at coordinates.

        Args:
            x: X coordinate
            y: Y coordinate
            button: Mouse button ("left", "right", or "middle")

        Raises:
            KVMError: If the double-click fails
        """
        try:
            self._client.mouse_click(self._device_id, button=button, double=True, x=x, y=y)
        except KVMClientError as e:
            raise self._wrap_error(e, "Double-click") from e

    def move(self, x: int, y: int) -> None:
        """Move mouse to coordinates.

        Args:
            x: X coordinate
            y: Y coordinate

        Raises:
            KVMError: If the move fails
        """
        try:
            self._client.mouse_move(self._device_id, x, y)
        except KVMClientError as e:
            raise self._wrap_error(e, "Move") from e

    def scroll(self, x: int, y: int, delta_x: int = 0, delta_y: int = 0) -> None:
        """Scroll at coordinates.

        Args:
            x: X coordinate
            y: Y coordinate
            delta_x: Horizontal scroll amount (currently unused)
            delta_y: Vertical scroll amount (positive = down)

        Raises:
            KVMError: If the scroll fails
        """
        try:
            # Move to position first, then scroll
            if x != 0 or y != 0:
                self._client.mouse_move(self._device_id, x, y)
            # The underlying API uses "amount" where positive = up
            self._client.mouse_scroll(self._device_id, -delta_y)
        except KVMClientError as e:
            raise self._wrap_error(e, "Scroll") from e

    def type_text(self, text: str) -> None:
        """Type text as if from keyboard.

        Args:
            text: Text to type

        Raises:
            KVMError: If typing fails
        """
        try:
            self._client.keyboard_type(self._device_id, text)
        except KVMClientError as e:
            raise self._wrap_error(e, "Type text") from e

    def key(self, key: str, modifiers: list[str] | None = None) -> None:
        """Press a key with optional modifiers.

        Args:
            key: Key to press (e.g., "Enter", "Tab", "a", "F1")
            modifiers: List of modifiers (e.g., ["ctrl"], ["ctrl", "shift"])

        Raises:
            KVMError: If key press fails
        """
        try:
            self._client.keyboard_press(self._device_id, key, modifiers)
        except KVMClientError as e:
            raise self._wrap_error(e, "Key press") from e

    def screenshot(self, format: str = "png") -> Screenshot:
        """Capture a screenshot.

        Args:
            format: Image format (currently only "png" supported by device)

        Returns:
            Screenshot object with image data

        Raises:
            KVMError: If screenshot fails
        """
        try:
            data = self._client.capture_screenshot(self._device_id)
            return Screenshot(data, format)
        except KVMClientError as e:
            raise self._wrap_error(e, "Screenshot") from e

    def health_check(self) -> dict:
        """Check if device is healthy.

        Returns:
            Health status dict from device

        Raises:
            KVMError: If health check fails
        """
        try:
            return self._client.health_check(self._device_id)
        except KVMClientError as e:
            raise self._wrap_error(e, "Health check") from e

    def __repr__(self) -> str:
        if self._device_id.startswith("_adhoc_"):
            return f"KVM(host={self.host!r}, port={self.port})"
        return f"KVM(device_id={self._device_id!r}, host={self.host!r})"
