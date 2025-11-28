#!/bin/bash
# Generate CA and client certificates for GLKVM MCP
# Run once on your local machine

set -e

# Default paths
CERTS_DIR="${GLKVM_CERTS_DIR:-$HOME/.config/glkvm-mcp/certs}"

# Certificate validity (10 years)
DAYS=3650

echo "=== GLKVM Certificate Generator ==="
echo ""
echo "This will create certificates in: $CERTS_DIR"
echo ""

# Create directory
mkdir -p "$CERTS_DIR"
cd "$CERTS_DIR"

# Check if CA already exists
if [ -f "ca.crt" ]; then
    echo "Warning: CA certificate already exists!"
    read -p "Overwrite? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Aborted."
        exit 1
    fi
fi

echo "Step 1: Generating CA private key..."
openssl genrsa -out ca.key 4096

echo "Step 2: Creating CA certificate..."
openssl req -new -x509 -days $DAYS -key ca.key -out ca.crt \
    -subj "/CN=GLKVM CA/O=GLKVM"

echo "Step 3: Generating client private key..."
openssl genrsa -out client.key 4096

echo "Step 4: Creating client certificate signing request..."
openssl req -new -key client.key -out client.csr \
    -subj "/CN=GLKVM Client/O=GLKVM"

echo "Step 5: Signing client certificate with CA..."
openssl x509 -req -days $DAYS -in client.csr -CA ca.crt -CAkey ca.key \
    -CAcreateserial -out client.crt

# Clean up CSR
rm -f client.csr

# Set permissions
chmod 600 ca.key client.key
chmod 644 ca.crt client.crt

echo ""
echo "=== Certificates Generated ==="
echo ""
echo "Files created in $CERTS_DIR:"
echo "  ca.crt      - CA certificate (copy to KVM devices)"
echo "  ca.key      - CA private key (keep secure, used to sign KVM certs)"
echo "  client.crt  - Client certificate (used by MCP server)"
echo "  client.key  - Client private key (used by MCP server)"
echo ""
echo "Next steps:"
echo "  1. Run setup_kvm.sh on each KVM device"
echo "  2. When prompted, paste the contents of ca.crt"
echo ""
