#!/usr/bin/env bash
set -euo pipefail

CERT_DIR="rrag-auth-server/traefik/certs"
DOMAIN="${1:-localhost}"

mkdir -p "$CERT_DIR"

openssl req -x509 -nodes -days 365 \
  -newkey rsa:2048 \
  -keyout "$CERT_DIR/server.key" \
  -out "$CERT_DIR/server.crt" \
  -subj "/CN=$DOMAIN" \
  -addext "subjectAltName=DNS:$DOMAIN,DNS:*.$DOMAIN,IP:127.0.0.1"

echo "Self-signed certificate generated in $CERT_DIR for domain: $DOMAIN"
