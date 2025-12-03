import os
from typing import Any, Dict, List, Optional

from meraki_snapshot.client import MerakiClient
from meraki_snapshot.storage import load_network_payloads, list_snapshots, read_json


class RestoreResult:
    def __init__(self, snapshot: str, operations: List[Dict[str, str]], dry_run: bool):
        self.snapshot = snapshot
        self.operations = operations
        self.dry_run = dry_run


class RestoreManager:
    def __init__(self, client: MerakiClient, base_dir: str):
        self.client = client
        self.base_dir = base_dir

    def available_snapshots(self) -> List[str]:
        return list_snapshots(self.base_dir, self.client.org_id)

    def _snapshot_root(self, snapshot_ts: str) -> str:
        return os.path.join(self.base_dir, self.client.org_id, snapshot_ts)

    def load_snapshot(self, snapshot_ts: str) -> Dict[str, Any]:
        root = self._snapshot_root(snapshot_ts)
        index_path = os.path.join(root, "index.json")
        index = read_json(index_path)
        networks = load_network_payloads(root)
        return {"root": root, "index": index, "networks": networks}

    def restore(
        self,
        snapshot_ts: str,
        network_names: Optional[List[str]] = None,
        dry_run: bool = True,
    ) -> RestoreResult:
        snapshot = self.load_snapshot(snapshot_ts)
        operations: List[Dict[str, str]] = []

        for folder, payload in snapshot["networks"].items():
            net_info = payload["metadata"]["network"]
            net_name = net_info.get("name", folder)
            if network_names and net_name not in network_names:
                continue
            network_id = net_info["id"]
            planned_ops = self.client.apply_network_config(network_id, payload["config"])
            operations.append({"network": net_name, "operations": planned_ops})

        return RestoreResult(snapshot_ts, operations, dry_run=dry_run)
