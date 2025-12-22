#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT_DIR/terraform"

CONTROL_IPS=$(terraform output -json control_plane_public_ips | jq -r '.[]')
if [[ -z "$CONTROL_IPS" ]]; then
  echo "No control plane IPs found. Did you run terraform apply?" >&2
  exit 1
fi

cat > "$ROOT_DIR/ansible/inventories/inventory.ini" <<'INV'
[control_plane]
INV
for ip in $CONTROL_IPS; do
echo "$ip" >> "$ROOT_DIR/ansible/inventories/inventory.ini"
done

cat >> "$ROOT_DIR/ansible/inventories/inventory.ini" <<'INV'

[worker]
# Workers discovered dynamically via aws_ec2 inventory plugin if desired
INV

echo "Rendered $ROOT_DIR/ansible/inventories/inventory.ini"
