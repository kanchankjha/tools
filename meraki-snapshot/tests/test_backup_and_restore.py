import os
from typing import Any, Dict, List

from meraki_snapshot.backup import BackupManager
from meraki_snapshot.client import MerakiClient
from meraki_snapshot.restore import RestoreManager


class FakeClient(MerakiClient):
    def __init__(self):
        super().__init__(api_key="fake", org_id="12345", base_url="https://api.meraki.com/api/v1")
        self.applied: List[Dict[str, Any]] = []

    def get_organization(self) -> Dict[str, Any]:
        return {"id": "12345", "name": "Test Org"}

    def list_networks(self) -> List[Dict[str, Any]]:
        return [
            {"id": "N_1", "name": "HQ", "productTypes": ["appliance", "switch", "wireless"]},
            {"id": "N_2", "name": "Branch", "productTypes": ["appliance"]},
        ]

    def list_devices(self, network_id: str) -> List[Dict[str, Any]]:
        return [{"serial": f"Q2XX-{network_id}", "model": "MX68"}]

    def list_org_admins(self) -> List[Dict[str, Any]]:
        return [{"id": "A1", "email": "admin@example.com"}]

    def list_config_templates(self) -> List[Dict[str, Any]]:
        return [{"id": "T1", "name": "Default"}]

    def collect_network_config(self, network_id: str, product_types: List[str]) -> Dict[str, Any]:
        return {
            "appliance": {"vlans": [{"id": 1, "subnet": "10.0.0.0/24", "name": f"{network_id} vlan"}]},
            "wireless": {"ssids": [{"number": 0, "name": "Corp", "enabled": True}]},
        }

    def apply_network_config(self, network_id: str, config: Dict[str, Any]) -> List[str]:
        self.applied.append({"network_id": network_id, "config": config})
        return ["appliance.vlans planned", "wireless.ssids planned"]


def test_backup_creates_files(tmp_path):
    client = FakeClient()
    mgr = BackupManager(client, output_dir=tmp_path.as_posix())
    summary = mgr.snapshot()

    assert os.path.isdir(summary.root)
    index_path = os.path.join(summary.root, "index.json")
    assert os.path.isfile(index_path)
    hq_folder = os.path.join(summary.root, "hq")
    assert os.path.isfile(os.path.join(hq_folder, "metadata.json"))
    assert os.path.isfile(os.path.join(hq_folder, "config.json"))
    assert len(summary.networks) == 2


def test_restore_reads_snapshot(tmp_path):
    client = FakeClient()
    backup_mgr = BackupManager(client, output_dir=tmp_path.as_posix())
    summary = backup_mgr.snapshot()
    snapshot_ts = os.path.basename(summary.root)

    restore_client = FakeClient()
    restore_mgr = RestoreManager(restore_client, base_dir=tmp_path.as_posix())
    result = restore_mgr.restore(snapshot_ts, dry_run=True)

    assert result.snapshot == snapshot_ts
    assert len(result.operations) == 2
    assert result.dry_run is True
