import json
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


def timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def slugify(value: str) -> str:
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return value or "network"


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def write_json(path: str, data: Any) -> None:
    ensure_dir(os.path.dirname(path))
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=True)


def read_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def list_snapshots(base_dir: str, org_id: str) -> List[str]:
    org_root = os.path.join(base_dir, org_id)
    if not os.path.isdir(org_root):
        return []
    return sorted([entry for entry in os.listdir(org_root) if os.path.isdir(os.path.join(org_root, entry))])


class SnapshotWriter:
    def __init__(self, base_dir: str, org_id: str, snap_ts: Optional[str] = None):
        self.base_dir = base_dir
        self.org_id = org_id
        self.snap_ts = snap_ts or timestamp()
        self.root = os.path.join(base_dir, org_id, self.snap_ts)
        ensure_dir(self.root)

    def index_path(self) -> str:
        return os.path.join(self.root, "index.json")

    def write_index(self, payload: Dict[str, Any]) -> str:
        write_json(self.index_path(), payload)
        return self.index_path()

    def network_paths(self, network_name: str) -> Tuple[str, str]:
        folder = os.path.join(self.root, slugify(network_name))
        metadata_path = os.path.join(folder, "metadata.json")
        config_path = os.path.join(folder, "config.json")
        return metadata_path, config_path

    def write_network(self, network: Dict[str, Any], devices: List[Dict[str, Any]], config: Dict[str, Any]) -> None:
        metadata_path, config_path = self.network_paths(network.get("name", network.get("id", "network")))
        metadata_payload = {
            "network": network,
            "devices": devices,
        }
        write_json(metadata_path, metadata_payload)
        write_json(config_path, config)


def load_network_payloads(snapshot_root: str) -> Dict[str, Dict[str, Any]]:
    payloads: Dict[str, Dict[str, Any]] = {}
    for entry in os.listdir(snapshot_root):
        folder = os.path.join(snapshot_root, entry)
        if not os.path.isdir(folder):
            continue
        metadata_path = os.path.join(folder, "metadata.json")
        config_path = os.path.join(folder, "config.json")
        if os.path.isfile(metadata_path) and os.path.isfile(config_path):
            payloads[entry] = {
                "metadata": read_json(metadata_path),
                "config": read_json(config_path),
            }
    return payloads
