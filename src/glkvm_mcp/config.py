"""Configuration loading and management."""

import os
from pathlib import Path
from typing import Optional
import yaml


DEFAULT_CONFIG_PATH = Path.home() / ".config" / "glkvm-mcp" / "config.yaml"
DEFAULT_CERTS_DIR = Path.home() / ".config" / "glkvm-mcp" / "certs"
DEFAULT_PORT = 8443


class Device:
    """Represents a KVM device."""

    def __init__(self, device_id: str, ip: str, port: int = DEFAULT_PORT, name: Optional[str] = None):
        self.device_id = device_id
        self.ip = ip
        self.port = port
        self.name = name or device_id

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        d = {"ip": self.ip}
        if self.port != DEFAULT_PORT:
            d["port"] = self.port
        if self.name != self.device_id:
            d["name"] = self.name
        return d

    @property
    def url(self) -> str:
        """Get the base URL for this device."""
        return f"https://{self.ip}:{self.port}"


class Config:
    """Configuration manager."""

    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or Path(os.environ.get("GLKVM_CONFIG", DEFAULT_CONFIG_PATH))
        self.certs_dir = Path(os.environ.get("GLKVM_CERTS_DIR", DEFAULT_CERTS_DIR))
        self.default_port = DEFAULT_PORT
        self.devices: dict[str, Device] = {}

        self._load()

    def _load(self) -> None:
        """Load configuration from file."""
        if not self.config_path.exists():
            return

        with open(self.config_path) as f:
            data = yaml.safe_load(f) or {}

        # Load certs_dir
        if "certs_dir" in data:
            self.certs_dir = Path(data["certs_dir"]).expanduser()

        # Load default port
        if "default_port" in data:
            self.default_port = int(data["default_port"])

        # Load devices
        for device_id, device_data in data.get("devices", {}).items():
            self.devices[device_id] = Device(
                device_id=device_id,
                ip=device_data["ip"],
                port=device_data.get("port", self.default_port),
                name=device_data.get("name"),
            )

    def save(self) -> None:
        """Save configuration to file."""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "certs_dir": str(self.certs_dir),
            "default_port": self.default_port,
            "devices": {
                device_id: device.to_dict()
                for device_id, device in self.devices.items()
            },
        }

        with open(self.config_path, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)

    def get_device(self, device_id: str) -> Optional[Device]:
        """Get a device by ID."""
        return self.devices.get(device_id)

    def add_device(self, device_id: str, ip: str, port: Optional[int] = None, name: Optional[str] = None) -> Device:
        """Add a new device."""
        device = Device(
            device_id=device_id,
            ip=ip,
            port=port or self.default_port,
            name=name,
        )
        self.devices[device_id] = device
        self.save()
        return device

    def remove_device(self, device_id: str) -> bool:
        """Remove a device. Returns True if removed, False if not found."""
        if device_id in self.devices:
            del self.devices[device_id]
            self.save()
            return True
        return False

    def list_devices(self) -> list[Device]:
        """List all devices."""
        return list(self.devices.values())

    @property
    def ca_cert_path(self) -> Path:
        """Path to CA certificate."""
        return self.certs_dir / "ca.crt"

    @property
    def client_cert_path(self) -> Path:
        """Path to client certificate."""
        return self.certs_dir / "client.crt"

    @property
    def client_key_path(self) -> Path:
        """Path to client private key."""
        return self.certs_dir / "client.key"
