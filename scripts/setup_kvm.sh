#!/bin/bash
# Setup script for GLKVM HID Server on KVM devices
# Download and run: curl -sSL https://raw.githubusercontent.com/davewking/glkvm-mcp/main/scripts/setup_kvm.sh | bash

set -e

GLKVM_DIR="/etc/glkvm"
CERTS_DIR="$GLKVM_DIR/certs"
HID_SERVER_URL="https://raw.githubusercontent.com/davewking/glkvm-mcp/main/kvm/hid_server.py"
SERVICE_NAME="glkvm-hid"

echo "=== GLKVM HID Server Setup ==="
echo ""

# Check for root
if [ "$EUID" -ne 0 ]; then
    echo "Please run as root (sudo)"
    exit 1
fi

# Step 1: Device ID
echo "Step 1: Device ID"
read -p "  Enter a unique ID for this KVM (e.g., kvm-office): " DEVICE_ID

if [ -z "$DEVICE_ID" ]; then
    echo "Error: Device ID cannot be empty"
    exit 1
fi

# Create directories
mkdir -p "$CERTS_DIR"

# Step 2: CA Certificate
echo ""
echo "Step 2: CA Certificate"
echo "  Paste your CA certificate (from ~/.config/glkvm-mcp/certs/ca.crt)"
echo "  End with an empty line:"
echo ""

CA_CERT=""
while IFS= read -r line; do
    [ -z "$line" ] && break
    CA_CERT="${CA_CERT}${line}"$'\n'
done

echo "$CA_CERT" > "$CERTS_DIR/ca.crt"
echo "  ✓ CA certificate saved to $CERTS_DIR/ca.crt"

# Step 3: Generate server certificate
echo ""
echo "Step 3: Generate Server Certificate"
echo "  Generating server key and CSR..."

openssl genrsa -out "$CERTS_DIR/server.key" 4096 2>/dev/null
openssl req -new -key "$CERTS_DIR/server.key" -out "$CERTS_DIR/server.csr" \
    -subj "/CN=$DEVICE_ID/O=GLKVM" 2>/dev/null

echo "  ✓ Server key saved to $CERTS_DIR/server.key"
echo ""
echo "  === ACTION REQUIRED ==="
echo "  Run this on your LOCAL machine to sign the certificate:"
echo ""
echo "  echo '$(cat "$CERTS_DIR/server.csr")' | \\"
echo "  openssl x509 -req -CA ~/.config/glkvm-mcp/certs/ca.crt \\"
echo "    -CAkey ~/.config/glkvm-mcp/certs/ca.key \\"
echo "    -CAcreateserial -days 3650 -out /dev/stdout 2>/dev/null"
echo ""
echo "  Then paste the signed certificate here (end with empty line):"
echo ""

SERVER_CERT=""
while IFS= read -r line; do
    [ -z "$line" ] && break
    SERVER_CERT="${SERVER_CERT}${line}"$'\n'
done

echo "$SERVER_CERT" > "$CERTS_DIR/server.crt"
rm -f "$CERTS_DIR/server.csr"
echo "  ✓ Server certificate saved to $CERTS_DIR/server.crt"

# Set permissions
chmod 600 "$CERTS_DIR/server.key"
chmod 644 "$CERTS_DIR/ca.crt" "$CERTS_DIR/server.crt"

# Step 4: Install HID Server
echo ""
echo "Step 4: Install HID Server"
echo "  Downloading hid_server.py..."

curl -sSL "$HID_SERVER_URL" -o /usr/local/bin/glkvm-hid-server
chmod +x /usr/local/bin/glkvm-hid-server

echo "  ✓ Installed to /usr/local/bin/glkvm-hid-server"

# Step 5: Create systemd service
echo ""
echo "Step 5: Create systemd service"

cat > "/etc/systemd/system/${SERVICE_NAME}.service" << EOF
[Unit]
Description=GLKVM HID Server
After=network.target

[Service]
Type=simple
ExecStart=/usr/local/bin/glkvm-hid-server --port 8443 --tls --cert $CERTS_DIR/server.crt --key $CERTS_DIR/server.key --ca $CERTS_DIR/ca.crt
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable "$SERVICE_NAME"
systemctl start "$SERVICE_NAME"

echo "  ✓ Created and started $SERVICE_NAME service"

# Get IP address
IP_ADDR=$(hostname -I | awk '{print $1}')

echo ""
echo "=== Setup Complete ==="
echo ""
echo "  Device ID: $DEVICE_ID"
echo "  Listening: https://0.0.0.0:8443"
echo "  IP Address: $IP_ADDR"
echo ""
echo "  Add to your local ~/.config/glkvm-mcp/config.yaml:"
echo ""
echo "  devices:"
echo "    $DEVICE_ID:"
echo "      ip: $IP_ADDR"
echo "      name: \"$DEVICE_ID\""
echo ""
echo "  To check status: systemctl status $SERVICE_NAME"
echo "  To view logs: journalctl -u $SERVICE_NAME -f"
echo ""
