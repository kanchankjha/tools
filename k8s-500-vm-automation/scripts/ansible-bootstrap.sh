#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT_DIR/ansible"

if ! ansible-galaxy collection install -r collections/requirements.yml; then
  echo "Failed to install collections" >&2
  exit 1
fi

echo "Ansible bootstrap complete"
