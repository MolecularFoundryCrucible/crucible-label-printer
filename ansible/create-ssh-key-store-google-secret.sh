#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="mf-crucible"          # <-- set this
PRIVATE_SECRET_NAME="crucible-print-ssh-key"
PUBLIC_SECRET_NAME="crucible-print-ssh-key-pub"
KEY_COMMENT="crucible-print-ssh-key-for-ansible"
TMPDIR="$(mktemp -d)"
trap 'rm -rf "$TMPDIR"' EXIT

PRIVATE_KEY="$TMPDIR/id_ed25519"
PUBLIC_KEY="$TMPDIR/id_ed25519.pub"

# Generate an ed25519 keypair with no passphrase (agent/automation use)
ssh-keygen -t ed25519 -C "$KEY_COMMENT" -f "$PRIVATE_KEY" -N "" -q

# Helper: create secret if missing, otherwise add a new version
store_secret() {
  local name="$1" file="$2"
  if gcloud secrets describe "$name" --project="$PROJECT_ID" >/dev/null 2>&1; then
    echo "Secret '$name' exists — adding a new version."
    gcloud secrets versions add "$name" --data-file="$file" --project="$PROJECT_ID"
  else
    echo "Creating secret '$name'."
    gcloud secrets create "$name" \
      --replication-policy="automatic" \
      --data-file="$file" \
      --project="$PROJECT_ID"
  fi
}

store_secret "$PRIVATE_SECRET_NAME" "$PRIVATE_KEY"
store_secret "$PUBLIC_SECRET_NAME"  "$PUBLIC_KEY"

echo
echo "Both keys stored in project '$PROJECT_ID'."
echo "  Private: $PRIVATE_SECRET_NAME"
echo "  Public:  $PUBLIC_SECRET_NAME"
echo
echo "Public key contents:"
echo "----------------------------------------------------------------"
cat "$PUBLIC_KEY"
echo "----------------------------------------------------------------"