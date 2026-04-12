#!/bin/sh
CERT_DIR=/etc/haproxy/certs
CERT_FILE=$CERT_DIR/union.pem

if [ ! -f "$CERT_FILE" ]; then
  mkdir -p "$CERT_DIR"
  openssl req -x509 -newkey rsa:2048 -keyout /tmp/key.pem -out /tmp/cert.pem \
    -days 365 -nodes -subj "/CN=union.local"
  cat /tmp/cert.pem /tmp/key.pem > "$CERT_FILE"
  rm -f /tmp/key.pem /tmp/cert.pem
  echo "Self-signed certificate generated."
fi

exec haproxy -f /usr/local/etc/haproxy/haproxy.cfg "$@"
