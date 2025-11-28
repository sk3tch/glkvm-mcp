# GLKVM MCP Server Design

## Overview

A simplified, all-Python MCP server for controlling KVM devices directly over HTTPS with mutual TLS (client certificate) authentication. No proxy server - the MCP server connects directly to HID servers running on each KVM device.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      Your Local Machine                         │
│  ┌───────────────┐      ┌─────────────────────────────────────┐ │
│  │  Claude Code  │─────▶│         Python MCP Server           │ │
│  │   (stdio)     │      │  • Tools: screenshot, mouse, kbd,   │ │
│  └───────────────┘      │    OCR, find_and_click, scroll      │ │
│                         │  • Device management tools          │ │
│                         │  • Tesseract OCR (local)            │ │
│                         └──────────────┬──────────────────────┘ │
│                                        │ HTTPS + mTLS           │
│  ~/.config/glkvm-mcp/                  │ (client cert auth)     │
│  ├── config.yaml (device list)         │                        │
│  └── certs/                            │                        │
│      ├── ca.crt                        │                        │
│      ├── client.crt                    │                        │
│      └── client.key                    │                        │
└────────────────────────────────────────┼────────────────────────┘
                                         │
            ┌────────────────────────────┼────────────────────────┐
            │                            ▼                        │
            │    ┌──────────────────────────────────────────────┐ │
            │    │           KVM Device (GL.iNet)               │ │
            │    │  ┌────────────────────────────────────────┐  │ │
            │    │  │     Python HID Server (port 8443)      │  │ │
            │    │  │  • mTLS server (validates client)      │  │ │
            │    │  │  • /mouse/move, /mouse/click           │  │ │
            │    │  │  • /keyboard/type, /keyboard/press     │  │ │
            │    │  │  • /screenshot                         │  │ │
            │    │  └──────────────┬─────────────────────────┘  │ │
            │    │                 │                            │ │
            │    │    ┌────────────┴────────────┐               │ │
            │    │    ▼                         ▼               │ │
            │    │ /dev/hidg0              /dev/hidg1           │ │
            │    │ (keyboard)              (mouse)              │ │
            │    └──────────────────────────────────────────────┘ │
            │                    Network                          │
            └─────────────────────────────────────────────────────┘
```

## MCP Tools

### Core Input/Output Tools

| Tool | Description | Key Parameters |
|------|-------------|----------------|
| `kvm_capture_screen` | Capture screenshot as base64 JPEG | `device_id` |
| `kvm_mouse_move` | Move cursor to absolute position | `device_id`, `x`, `y` |
| `kvm_mouse_click` | Click mouse button | `device_id`, `button?`, `x?`, `y?`, `double?` |
| `kvm_mouse_scroll` | Scroll wheel | `device_id`, `amount` |
| `kvm_keyboard_type` | Type a text string | `device_id`, `text` |
| `kvm_keyboard_press` | Press key/combo (e.g., `Ctrl+C`) | `device_id`, `key`, `modifiers?` |

### OCR & Convenience Tools

| Tool | Description | Key Parameters |
|------|-------------|----------------|
| `kvm_screenshot_with_ocr` | Screenshot + extracted text + bounding boxes | `device_id` |
| `kvm_find_and_click` | Find text on screen and click it | `device_id`, `text`, `click?` |

### Device Management Tools

| Tool | Description | Key Parameters |
|------|-------------|----------------|
| `kvm_list_devices` | List all configured KVM devices | (none) |
| `kvm_add_device` | Add a new KVM device to config | `device_id`, `ip`, `port?`, `name?` |
| `kvm_remove_device` | Remove a device from config | `device_id` |

**Notes:**
- All tools require `device_id` except `kvm_list_devices`
- Coordinates use 0-32767 HID range
- `kvm_find_and_click` with `click=false` returns coordinates without clicking

## Certificate Structure

### Local Machine (`~/.config/glkvm-mcp/certs/`)

```
├── ca.crt              # CA certificate (created once)
├── ca.key              # CA private key (keep secure, signs certs)
├── client.crt          # Client cert (signed by CA, sent to KVMs)
└── client.key          # Client private key (used for mTLS)
```

### KVM Device (`/etc/glkvm/certs/`)

```
├── ca.crt              # Same CA cert (validates client)
├── server.crt          # Server cert (signed by CA, unique per KVM)
└── server.key          # Server private key
```

## Certificate Setup Flow

### Initial Setup (One-time on local machine)

```bash
./scripts/generate_certs.sh
# Creates CA + client cert in ~/.config/glkvm-mcp/certs/
```

### KVM Setup Flow

1. SSH into new KVM device
2. Run: `curl -sSL https://raw.githubusercontent.com/davewking/glkvm-mcp/main/scripts/setup_kvm.sh | bash`
3. Script prompts for device ID and CA certificate
4. Script generates server key + CSR
5. User signs CSR locally with CA key, pastes signed cert back
6. Script installs HID server and creates systemd service
7. User adds device to local `config.yaml`

## Config File Format

```yaml
# ~/.config/glkvm-mcp/config.yaml

# Certificate paths (optional, defaults shown)
certs_dir: ~/.config/glkvm-mcp/certs

# Default port for KVM devices (optional, default: 8443)
default_port: 8443

# Configured KVM devices
devices:
  kvm-office:
    ip: 192.168.1.31
    port: 8443           # optional, uses default_port if omitted
    name: "Office PC"    # optional friendly name

  kvm-server:
    ip: 192.168.1.32
    name: "Home Server"
```

**Environment overrides:**
- `GLKVM_CONFIG` - Config file path
- `GLKVM_CERTS_DIR` - Certificates directory

## HID Server API

Endpoints over HTTPS with mTLS on port 8443:

| Endpoint | Method | Body | Description |
|----------|--------|------|-------------|
| `/health` | GET | - | Health check |
| `/screenshot` | GET | - | Capture JPEG screenshot |
| `/mouse/move` | POST | `{"x": int, "y": int}` | Move cursor (0-32767) |
| `/mouse/click` | POST | `{"button": str, "double": bool, "x"?: int, "y"?: int}` | Click |
| `/mouse/scroll` | POST | `{"amount": int}` | Scroll wheel |
| `/keyboard/type` | POST | `{"text": str}` | Type text |
| `/keyboard/press` | POST | `{"key": str, "modifiers"?: [str]}` | Press key combo |

**Response format:**
```json
{"success": true, "data": ...}
{"success": false, "error": "description"}
```

## Repository Structure

```
glkvm-mcp/
├── src/
│   └── glkvm_mcp/
│       ├── __init__.py
│       ├── server.py         # MCP server (stdio JSON-RPC)
│       ├── client.py         # HTTPS client to KVM HID servers
│       ├── tools.py          # MCP tool definitions & handlers
│       ├── config.py         # Config file loading/saving
│       └── ocr.py            # Tesseract wrapper
│
├── kvm/
│   └── hid_server.py         # HID server (runs on KVM device)
│
├── scripts/
│   ├── setup_kvm.sh          # KVM provisioning script
│   └── generate_certs.sh     # Local CA & client cert generation
│
├── config.example.yaml       # Example config
├── pyproject.toml            # Python package config
├── requirements.txt          # Dependencies
├── README.md                 # Setup & usage instructions
├── LICENSE                   # Open source license
└── .gitignore
```

## Dependencies

```
pytesseract>=0.3.10    # OCR
Pillow>=10.0.0         # Image handling
PyYAML>=6.0            # Config parsing
```

## Gitignored Files

```
config.yaml
*.crt
*.key
*.pem
__pycache__/
*.pyc
.env
```

## Future Additions (Not in Initial Version)

- Python SDK execution (`kvm_run_script`)
- Screen comparison (`kvm_compare_screen`)
- WebSocket persistent connections
- SSH fallback
