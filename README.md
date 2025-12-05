# GLKVM MCP Server

A Python MCP server for controlling KVM devices directly over HTTPS with mutual TLS (client certificate) authentication.  This allows Claude and other agents to drive GUIs on other computers.  This opens up being able to drive GUIs on places where Claude isn't installed, or can't be installed.  For example, if you wanted to have Claude help you automate an OS install or BIOS configuration, you could do that.  There's of course the question of _should_ you do that.  As a security person it was somewhat terrifying to see how easy this was to build and how well it works.

## Features

- **Direct connection** - No proxy server, connects directly to KVM devices
- **mTLS authentication** - Client certificates for secure access
- **10 MCP tools** - Screenshot, mouse, keyboard, OCR, device management
- **Local OCR** - Tesseract runs locally, no cloud APIs needed
- **Simple setup** - One script to provision new KVM devices

## Prerequisites

### Local Machine (where MCP server runs)

- Python 3.10+
- Tesseract OCR: `apt install tesseract-ocr` or `brew install tesseract`
- ffmpeg: `apt install ffmpeg` or `brew install ffmpeg`

### KVM Device

- Linux with USB HID gadget support (GL.iNet, Raspberry Pi, etc.)
- ustreamer running for video capture
- Python 3

## Installation

```bash
# Clone the repository
git clone https://github.com/sk3tch/glkvm-mcp.git
cd glkvm-mcp

# Install Python dependencies
pip install -r requirements.txt

# Generate certificates (one-time)
./scripts/generate_certs.sh
```

## KVM Device Setup

On each KVM device:

```bash
curl -sSL https://raw.githubusercontent.com/sk3tch/glkvm-mcp/main/scripts/setup_kvm.sh | sudo bash
```

The script will:
1. Ask for a device ID
2. Ask for your CA certificate
3. Generate a server certificate (you'll sign it with your CA)
4. Install and start the HID server

## Configuration

Create `~/.config/glkvm-mcp/config.yaml`:

```yaml
devices:
  kvm-office:
    ip: 192.168.1.31
    name: "Office PC"

  kvm-server:
    ip: 192.168.1.32
    name: "Home Server"
```

## Usage with Claude Code

Add to your Claude Code MCP settings:

```json
{
  "mcpServers": {
    "glkvm": {
      "command": "python",
      "args": ["-m", "glkvm_mcp.server"],
      "cwd": "/path/to/glkvm-mcp/src"
    }
  }
}
```

Or if installed as a package:

```json
{
  "mcpServers": {
    "glkvm": {
      "command": "glkvm-mcp"
    }
  }
}
```

## Available Tools

| Tool | Description |
|------|-------------|
| `kvm_list_devices` | List all configured KVM devices |
| `kvm_add_device` | Add a new KVM device |
| `kvm_remove_device` | Remove a KVM device |
| `kvm_capture_screen` | Capture screenshot (base64 JPEG) |
| `kvm_screenshot_with_ocr` | Screenshot + OCR text extraction |
| `kvm_find_and_click` | Find text on screen and click it |
| `kvm_mouse_move` | Move cursor (0-32767 coordinates) |
| `kvm_mouse_click` | Click mouse button |
| `kvm_mouse_scroll` | Scroll mouse wheel |
| `kvm_keyboard_type` | Type text string |
| `kvm_keyboard_press` | Press key/combo (e.g., Ctrl+C) |

## License

MIT
