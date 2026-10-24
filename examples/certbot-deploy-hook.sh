#!/usr/bin/env bash
# Put on each certbot server, e.g. /etc/letsencrypt/renewal-hooks/deploy/notify.sh
# (chmod +x). Certbot runs it only after a successful renewal and sets
# RENEWED_DOMAINS. Reload your web server first so the new cert is being served.
set -euo pipefail

NOTIFIER_URL="${NOTIFIER_URL:-http://notifier.internal:8000/hook-receiver/hook}"

# systemctl reload nginx || true

for domain in ${RENEWED_DOMAINS:-}; do
  curl -fsS -m 10 -X POST "$NOTIFIER_URL" \
    -H "Content-Type: application/json" \
    -d "{\"status\": \"success\", \"domain\": \"${domain}\"}" || true
done

# To report a failure from your own wrapper:
#   curl -fsS -X POST "$NOTIFIER_URL" -H "Content-Type: application/json" \
#     -d '{"status": "failed", "domain": "example.com"}'
