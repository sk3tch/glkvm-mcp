#!/usr/bin/env python3
"""
KVM HID Web Service
Lightweight HTTP server for mouse/keyboard control via USB HID gadget.
Runs directly on the GL.iNet KVM device.

Usage:
    ./kvm-hid-server.py [--port 8080] [--auth user:pass]
    ./kvm-hid-server.py --port 8443 --tls --cert server.crt --key server.key --ca ca.crt

Endpoints:
    POST /mouse/move      {"x": 16383, "y": 16383}
    POST /mouse/click     {"button": "left", "double": false, "x": 16383, "y": 16383}
    POST /mouse/scroll    {"amount": 5}
    POST /keyboard/type   {"text": "hello world"}
    POST /keyboard/press  {"key": "enter", "modifiers": ["ctrl"]}
    GET  /health          Health check
    GET  /screenshot       Get H.264 keyframes (caller converts to JPEG)
"""

import json
import subprocess
import struct
import time
import argparse
import base64
import ssl
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

# HID devices
KEYBOARD_DEVICE = "/dev/hidg0"
MOUSE_DEVICE = "/dev/hidg1"

# Coordinate range
MAX_COORD = 32767

# USB HID modifier keys
MODIFIERS = {
    'ctrl': 0x01, 'shift': 0x02, 'alt': 0x04, 'meta': 0x08,
    'right_ctrl': 0x10, 'right_shift': 0x20, 'right_alt': 0x40, 'right_meta': 0x80,
}

# USB HID keycodes
KEYCODES = {
    'a': 0x04, 'b': 0x05, 'c': 0x06, 'd': 0x07, 'e': 0x08, 'f': 0x09,
    'g': 0x0a, 'h': 0x0b, 'i': 0x0c, 'j': 0x0d, 'k': 0x0e, 'l': 0x0f,
    'm': 0x10, 'n': 0x11, 'o': 0x12, 'p': 0x13, 'q': 0x14, 'r': 0x15,
    's': 0x16, 't': 0x17, 'u': 0x18, 'v': 0x19, 'w': 0x1a, 'x': 0x1b,
    'y': 0x1c, 'z': 0x1d,
    '1': 0x1e, '2': 0x1f, '3': 0x20, '4': 0x21, '5': 0x22,
    '6': 0x23, '7': 0x24, '8': 0x25, '9': 0x26, '0': 0x27,
    'enter': 0x28, 'esc': 0x29, 'backspace': 0x2a, 'tab': 0x2b, 'space': 0x2c,
    '-': 0x2d, '=': 0x2e, '[': 0x2f, ']': 0x30, '\\': 0x31,
    ';': 0x33, "'": 0x34, '`': 0x35, ',': 0x36, '.': 0x37, '/': 0x38,
    'capslock': 0x39,
    'f1': 0x3a, 'f2': 0x3b, 'f3': 0x3c, 'f4': 0x3d, 'f5': 0x3e, 'f6': 0x3f,
    'f7': 0x40, 'f8': 0x41, 'f9': 0x42, 'f10': 0x43, 'f11': 0x44, 'f12': 0x45,
    'printscreen': 0x46, 'scrolllock': 0x47, 'pause': 0x48,
    'insert': 0x49, 'home': 0x4a, 'pageup': 0x4b, 'delete': 0x4c,
    'end': 0x4d, 'pagedown': 0x4e,
    'right': 0x4f, 'left': 0x50, 'down': 0x51, 'up': 0x52,
}

# Characters requiring shift
SHIFT_CHARS = {
    '!': '1', '@': '2', '#': '3', '$': '4', '%': '5',
    '^': '6', '&': '7', '*': '8', '(': '9', ')': '0',
    '_': '-', '+': '=', '{': '[', '}': ']', '|': '\\',
    ':': ';', '"': "'", '~': '`', '<': ',', '>': '.', '?': '/',
}

# Global auth credentials
AUTH_CREDENTIALS = None


class ScreenCapture:
    """Screenshot capture using ustreamer-dump"""

    USTREAMER_SINK = "kvmd::ustreamer::h264"

    @staticmethod
    def capture_h264_frames(count=5, timeout=3):
        """Capture fresh H.264 keyframes using ustreamer-dump

        Returns raw H.264 data that can be converted to JPEG by caller.
        """
        cmd = [
            "ustreamer-dump",
            "--sink", ScreenCapture.USTREAMER_SINK,
            "--output", "-",
            "--count", str(count),
            "--key-required"
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=timeout
            )
            if result.returncode != 0:
                raise RuntimeError(f"ustreamer-dump failed: {result.stderr.decode()}")
            return result.stdout
        except subprocess.TimeoutExpired:
            raise RuntimeError("Screenshot capture timed out")
        except FileNotFoundError:
            raise RuntimeError("ustreamer-dump not found")


class HIDController:
    """Low-level HID device control"""

    @staticmethod
    def mouse_move(x, y):
        """Move mouse to absolute coordinates (0-32767)"""
        x = max(0, min(MAX_COORD, int(x)))
        y = max(0, min(MAX_COORD, int(y)))
        report = struct.pack('<Bhhbb', 0, x, y, 0, 0)
        with open(MOUSE_DEVICE, 'wb') as f:
            f.write(report)

    @staticmethod
    def mouse_click(button='left', double=False, x=None, y=None):
        """Click mouse button, optionally at coordinates"""
        button_map = {'left': 0x01, 'right': 0x02, 'middle': 0x04}
        btn = button_map.get(button, 0x01)

        # Move first if coordinates provided
        if x is not None and y is not None:
            HIDController.mouse_move(x, y)
            time.sleep(0.01)

        with open(MOUSE_DEVICE, 'wb') as f:
            # Click down
            f.write(struct.pack('<Bhhbb', btn, 0, 0, 0, 0))
            f.flush()
            time.sleep(0.01)
            # Click up
            f.write(struct.pack('<Bhhbb', 0, 0, 0, 0, 0))

            if double:
                time.sleep(0.05)
                f.write(struct.pack('<Bhhbb', btn, 0, 0, 0, 0))
                f.flush()
                time.sleep(0.01)
                f.write(struct.pack('<Bhhbb', 0, 0, 0, 0, 0))

    @staticmethod
    def mouse_scroll(amount):
        """Scroll mouse wheel (-127 to 127)"""
        amount = max(-127, min(127, int(amount)))
        report = struct.pack('<Bhhbb', 0, 0, 0, amount, 0)
        with open(MOUSE_DEVICE, 'wb') as f:
            f.write(report)

    @staticmethod
    def keyboard_report(modifiers=0, keycode=0):
        """Send raw keyboard HID report"""
        report = struct.pack('8B', modifiers, 0, keycode, 0, 0, 0, 0, 0)
        with open(KEYBOARD_DEVICE, 'wb') as f:
            f.write(report)

    @staticmethod
    def keyboard_press(key, modifiers=None):
        """Press and release a key"""
        key_lower = key.lower()
        mod_byte = 0

        if modifiers:
            for mod in modifiers:
                mod_byte |= MODIFIERS.get(mod.lower(), 0)

        keycode = KEYCODES.get(key_lower, 0)

        # Handle uppercase and shift characters
        if keycode == 0 and len(key) == 1:
            if key.isupper():
                mod_byte |= MODIFIERS['shift']
                keycode = KEYCODES.get(key_lower, 0)
            elif key in SHIFT_CHARS:
                mod_byte |= MODIFIERS['shift']
                keycode = KEYCODES.get(SHIFT_CHARS[key], 0)

        if keycode:
            HIDController.keyboard_report(mod_byte, keycode)
            time.sleep(0.01)
            HIDController.keyboard_report(0, 0)
            time.sleep(0.01)

    @staticmethod
    def keyboard_type(text):
        """Type a string of text"""
        for char in text:
            if char == '\n':
                HIDController.keyboard_press('enter')
            elif char == ' ':
                HIDController.keyboard_press('space')
            else:
                HIDController.keyboard_press(char)


class HIDRequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler for HID control"""

    def log_message(self, format, *args):
        """Suppress default logging"""
        pass

    def check_auth(self):
        """Check basic authentication"""
        if AUTH_CREDENTIALS is None:
            return True

        auth_header = self.headers.get('Authorization', '')
        if not auth_header.startswith('Basic '):
            return False

        try:
            decoded = base64.b64decode(auth_header[6:]).decode('utf-8')
            return decoded == AUTH_CREDENTIALS
        except:
            return False

    def send_json(self, data, status=200):
        """Send JSON response"""
        body = json.dumps(data).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', len(body))
        self.end_headers()
        self.wfile.write(body)

    def send_error_json(self, message, status=400):
        """Send error JSON response"""
        self.send_json({'success': False, 'error': message}, status)

    def read_json_body(self):
        """Read and parse JSON request body"""
        content_length = int(self.headers.get('Content-Length', 0))
        if content_length == 0:
            return {}
        body = self.rfile.read(content_length)
        return json.loads(body.decode('utf-8'))

    def do_GET(self):
        """Handle GET requests"""
        if not self.check_auth():
            self.send_error_json('Unauthorized', 401)
            return

        path = urlparse(self.path).path

        if path == '/health':
            self.send_json({'status': 'ok', 'service': 'kvm-hid-server'})

        elif path == '/screenshot':
            try:
                h264_data = ScreenCapture.capture_h264_frames()
                self.send_response(200)
                self.send_header('Content-Type', 'video/h264')
                self.send_header('Content-Length', len(h264_data))
                self.end_headers()
                self.wfile.write(h264_data)
            except Exception as e:
                self.send_error_json(f'Screenshot failed: {e}', 500)

        else:
            self.send_error_json('Not found', 404)

    def do_POST(self):
        """Handle POST requests"""
        if not self.check_auth():
            self.send_error_json('Unauthorized', 401)
            return

        path = urlparse(self.path).path

        try:
            data = self.read_json_body()
        except json.JSONDecodeError as e:
            self.send_error_json(f'Invalid JSON: {e}')
            return

        try:
            if path == '/mouse/move':
                x = data.get('x', 16383)
                y = data.get('y', 16383)
                HIDController.mouse_move(x, y)
                self.send_json({'success': True, 'action': 'mouse_move', 'x': x, 'y': y})

            elif path == '/mouse/click':
                button = data.get('button', 'left')
                double = data.get('double', False)
                x = data.get('x')
                y = data.get('y')
                HIDController.mouse_click(button, double, x, y)
                self.send_json({'success': True, 'action': 'mouse_click', 'button': button})

            elif path == '/mouse/scroll':
                amount = data.get('amount', 0)
                HIDController.mouse_scroll(amount)
                self.send_json({'success': True, 'action': 'mouse_scroll', 'amount': amount})

            elif path == '/keyboard/type':
                text = data.get('text', '')
                HIDController.keyboard_type(text)
                self.send_json({'success': True, 'action': 'keyboard_type', 'length': len(text)})

            elif path == '/keyboard/press':
                key = data.get('key', '')
                modifiers = data.get('modifiers', [])
                HIDController.keyboard_press(key, modifiers)
                self.send_json({'success': True, 'action': 'keyboard_press', 'key': key})

            else:
                self.send_error_json('Not found', 404)

        except Exception as e:
            self.send_error_json(f'HID error: {e}', 500)


def main():
    parser = argparse.ArgumentParser(description='KVM HID Web Service')
    parser.add_argument('--port', type=int, default=8080, help='Port to listen on')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to')
    parser.add_argument('--auth', help='Basic auth credentials (user:pass)')
    # TLS options
    parser.add_argument('--tls', action='store_true', help='Enable TLS')
    parser.add_argument('--cert', help='Server certificate file')
    parser.add_argument('--key', help='Server private key file')
    parser.add_argument('--ca', help='CA certificate for client verification (enables mTLS)')
    args = parser.parse_args()

    global AUTH_CREDENTIALS
    AUTH_CREDENTIALS = args.auth

    server = HTTPServer((args.host, args.port), HIDRequestHandler)

    # Setup TLS if enabled
    if args.tls:
        if not args.cert or not args.key:
            print('Error: --tls requires --cert and --key')
            return 1

        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(args.cert, args.key)

        # Enable client certificate verification (mTLS) if CA provided
        if args.ca:
            context.verify_mode = ssl.CERT_REQUIRED
            context.load_verify_locations(args.ca)
            print(f'mTLS enabled - client certificates required')
        else:
            context.verify_mode = ssl.CERT_NONE

        server.socket = context.wrap_socket(server.socket, server_side=True)
        print(f'KVM HID Server listening on https://{args.host}:{args.port}')
    else:
        print(f'KVM HID Server listening on http://{args.host}:{args.port}')

    if AUTH_CREDENTIALS:
        print(f'Basic auth enabled')

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nShutting down...')
        server.shutdown()


if __name__ == '__main__':
    main()
