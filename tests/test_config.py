"""Tests for configuration management."""

from pathlib import Path

import yaml

from glkvm_mcp.config import DEFAULT_PORT, Config, Device


class TestDevice:
    """Tests for Device class."""

    def test_device_init_defaults(self):
        """Device uses default port and name=device_id."""
        device = Device("my-kvm", "192.168.1.100")
        assert device.device_id == "my-kvm"
        assert device.ip == "192.168.1.100"
        assert device.port == DEFAULT_PORT
        assert device.name == "my-kvm"

    def test_device_init_custom_values(self):
        """Device accepts custom port and name."""
        device = Device("my-kvm", "192.168.1.100", port=9000, name="Office KVM")
        assert device.port == 9000
        assert device.name == "Office KVM"

    def test_device_to_dict_minimal(self):
        """to_dict omits defaults (port, matching name)."""
        device = Device("my-kvm", "192.168.1.100")
        d = device.to_dict()
        assert d == {"ip": "192.168.1.100"}
        assert "port" not in d
        assert "name" not in d

    def test_device_to_dict_includes_custom_port(self):
        """to_dict includes port when non-default."""
        device = Device("my-kvm", "192.168.1.100", port=9000)
        d = device.to_dict()
        assert d["port"] == 9000

    def test_device_to_dict_includes_custom_name(self):
        """to_dict includes name when different from device_id."""
        device = Device("my-kvm", "192.168.1.100", name="Office KVM")
        d = device.to_dict()
        assert d["name"] == "Office KVM"

    def test_device_to_dict_full(self):
        """to_dict includes all custom values."""
        device = Device("my-kvm", "192.168.1.100", port=9000, name="Office KVM")
        d = device.to_dict()
        assert d == {"ip": "192.168.1.100", "port": 9000, "name": "Office KVM"}

    def test_device_url_property(self):
        """url property returns https://ip:port."""
        device = Device("my-kvm", "192.168.1.100", port=9000)
        assert device.url == "https://192.168.1.100:9000"

    def test_device_url_default_port(self):
        """url property works with default port."""
        device = Device("my-kvm", "10.0.0.1")
        assert device.url == f"https://10.0.0.1:{DEFAULT_PORT}"


class TestConfigInit:
    """Tests for Config initialization."""

    def test_config_init_custom_path(self, tmp_path):
        """Config uses provided path."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("")
        config = Config(config_file)
        assert config.config_path == config_file

    def test_config_init_missing_file(self, tmp_path):
        """Config handles missing file gracefully."""
        config_file = tmp_path / "nonexistent.yaml"
        config = Config(config_file)
        assert config.devices == {}
        assert config.default_port == DEFAULT_PORT

    def test_config_init_empty_yaml(self, tmp_path):
        """Config handles empty/null YAML."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("")
        config = Config(config_file)
        assert config.devices == {}

    def test_config_init_null_yaml(self, tmp_path):
        """Config handles YAML with null content."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("null")
        config = Config(config_file)
        assert config.devices == {}

    def test_config_loads_devices(self, tmp_path):
        """Config parses devices from YAML."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("""
devices:
  kvm1:
    ip: 192.168.1.100
  kvm2:
    ip: 192.168.1.101
    port: 9000
    name: Second KVM
""")
        config = Config(config_file)
        assert len(config.devices) == 2
        assert config.devices["kvm1"].ip == "192.168.1.100"
        assert config.devices["kvm1"].port == DEFAULT_PORT
        assert config.devices["kvm2"].ip == "192.168.1.101"
        assert config.devices["kvm2"].port == 9000
        assert config.devices["kvm2"].name == "Second KVM"

    def test_config_loads_certs_dir(self, tmp_path):
        """Config reads certs_dir from file."""
        config_file = tmp_path / "config.yaml"
        certs_path = tmp_path / "my-certs"
        config_file.write_text(f"certs_dir: {certs_path}")
        config = Config(config_file)
        assert config.certs_dir == certs_path

    def test_config_loads_certs_dir_with_tilde(self, tmp_path):
        """Config expands ~ in certs_dir."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("certs_dir: ~/my-certs")
        config = Config(config_file)
        assert config.certs_dir == Path.home() / "my-certs"

    def test_config_loads_default_port(self, tmp_path):
        """Config reads default_port from file."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("default_port: 9999")
        config = Config(config_file)
        assert config.default_port == 9999

    def test_config_device_uses_config_default_port(self, tmp_path):
        """Devices use config's default_port when not specified."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("""
default_port: 7777
devices:
  kvm1:
    ip: 192.168.1.100
""")
        config = Config(config_file)
        assert config.devices["kvm1"].port == 7777


class TestConfigEnvironment:
    """Tests for Config environment variable handling."""

    def test_config_env_glkvm_config(self, tmp_path, monkeypatch):
        """Config respects GLKVM_CONFIG env var."""
        config_file = tmp_path / "env-config.yaml"
        config_file.write_text("default_port: 1111")
        monkeypatch.setenv("GLKVM_CONFIG", str(config_file))

        config = Config()  # No path provided
        assert config.config_path == config_file
        assert config.default_port == 1111

    def test_config_env_glkvm_certs_dir(self, tmp_path, monkeypatch):
        """Config respects GLKVM_CERTS_DIR env var."""
        certs_dir = tmp_path / "env-certs"
        monkeypatch.setenv("GLKVM_CERTS_DIR", str(certs_dir))

        config_file = tmp_path / "config.yaml"
        config_file.write_text("")
        config = Config(config_file)
        assert config.certs_dir == certs_dir

    def test_config_explicit_path_overrides_env(self, tmp_path, monkeypatch):
        """Explicit config_path overrides GLKVM_CONFIG env."""
        env_config = tmp_path / "env-config.yaml"
        env_config.write_text("default_port: 1111")
        explicit_config = tmp_path / "explicit-config.yaml"
        explicit_config.write_text("default_port: 2222")

        monkeypatch.setenv("GLKVM_CONFIG", str(env_config))

        config = Config(explicit_config)
        assert config.config_path == explicit_config
        assert config.default_port == 2222


class TestConfigDeviceOperations:
    """Tests for Config device CRUD operations."""

    def test_config_get_device_found(self, tmp_path):
        """get_device returns Device when found."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("""
devices:
  kvm1:
    ip: 192.168.1.100
""")
        config = Config(config_file)
        device = config.get_device("kvm1")
        assert device is not None
        assert device.ip == "192.168.1.100"

    def test_config_get_device_not_found(self, tmp_path):
        """get_device returns None when not found."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("")
        config = Config(config_file)
        assert config.get_device("nonexistent") is None

    def test_config_add_device_minimal(self, tmp_path):
        """add_device creates device with minimal args."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("")
        config = Config(config_file)

        device = config.add_device("new-kvm", "10.0.0.1")
        assert device.device_id == "new-kvm"
        assert device.ip == "10.0.0.1"
        assert device.port == DEFAULT_PORT
        assert "new-kvm" in config.devices

    def test_config_add_device_full(self, tmp_path):
        """add_device accepts port and name."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("")
        config = Config(config_file)

        device = config.add_device("new-kvm", "10.0.0.1", port=9000, name="New KVM")
        assert device.port == 9000
        assert device.name == "New KVM"

    def test_config_add_device_saves(self, tmp_path):
        """add_device persists to file."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("")
        config = Config(config_file)
        config.add_device("new-kvm", "10.0.0.1")

        # Reload and verify
        config2 = Config(config_file)
        assert "new-kvm" in config2.devices

    def test_config_remove_device_exists(self, tmp_path):
        """remove_device returns True and removes existing device."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("""
devices:
  kvm1:
    ip: 192.168.1.100
""")
        config = Config(config_file)
        result = config.remove_device("kvm1")
        assert result is True
        assert "kvm1" not in config.devices

    def test_config_remove_device_not_exists(self, tmp_path):
        """remove_device returns False for nonexistent device."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("")
        config = Config(config_file)
        result = config.remove_device("nonexistent")
        assert result is False

    def test_config_remove_device_saves(self, tmp_path):
        """remove_device persists to file."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("""
devices:
  kvm1:
    ip: 192.168.1.100
""")
        config = Config(config_file)
        config.remove_device("kvm1")

        # Reload and verify
        config2 = Config(config_file)
        assert "kvm1" not in config2.devices

    def test_config_list_devices_multiple(self, tmp_path):
        """list_devices returns all devices."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("""
devices:
  kvm1:
    ip: 192.168.1.100
  kvm2:
    ip: 192.168.1.101
""")
        config = Config(config_file)
        devices = config.list_devices()
        assert len(devices) == 2
        device_ids = [d.device_id for d in devices]
        assert "kvm1" in device_ids
        assert "kvm2" in device_ids

    def test_config_list_devices_empty(self, tmp_path):
        """list_devices returns empty list when no devices."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("")
        config = Config(config_file)
        assert config.list_devices() == []


class TestConfigSave:
    """Tests for Config.save()."""

    def test_config_save_creates_directories(self, tmp_path):
        """save creates parent directories if needed."""
        config_file = tmp_path / "deep" / "nested" / "config.yaml"
        config = Config(config_file)
        config.add_device("kvm1", "192.168.1.100")

        assert config_file.exists()
        assert config_file.parent.exists()

    def test_config_save_yaml_format(self, tmp_path):
        """save writes valid YAML."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("")
        config = Config(config_file)
        config.add_device("kvm1", "192.168.1.100", port=9000, name="Test KVM")

        # Parse the saved YAML
        with config_file.open() as f:
            data = yaml.safe_load(f)

        assert "devices" in data
        assert "kvm1" in data["devices"]
        assert data["devices"]["kvm1"]["ip"] == "192.168.1.100"
        assert data["devices"]["kvm1"]["port"] == 9000
        assert data["devices"]["kvm1"]["name"] == "Test KVM"


class TestConfigCertPaths:
    """Tests for Config certificate path properties."""

    def test_config_ca_cert_path(self, tmp_path):
        """ca_cert_path returns correct path."""
        config_file = tmp_path / "config.yaml"
        certs_dir = tmp_path / "certs"
        config_file.write_text(f"certs_dir: {certs_dir}")
        config = Config(config_file)
        assert config.ca_cert_path == certs_dir / "ca.crt"

    def test_config_client_cert_path(self, tmp_path):
        """client_cert_path returns correct path."""
        config_file = tmp_path / "config.yaml"
        certs_dir = tmp_path / "certs"
        config_file.write_text(f"certs_dir: {certs_dir}")
        config = Config(config_file)
        assert config.client_cert_path == certs_dir / "client.crt"

    def test_config_client_key_path(self, tmp_path):
        """client_key_path returns correct path."""
        config_file = tmp_path / "config.yaml"
        certs_dir = tmp_path / "certs"
        config_file.write_text(f"certs_dir: {certs_dir}")
        config = Config(config_file)
        assert config.client_key_path == certs_dir / "client.key"
