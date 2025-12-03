import os
from unittest.mock import Mock, patch

import pytest

from meraki_snapshot.restore import RestoreManager, RestoreResult


class TestRestoreResult:
    def test_initialization(self):
        operations = [{"network": "HQ", "operations": ["test"]}]
        result = RestoreResult("20231201T120000Z", operations, dry_run=True)

        assert result.snapshot == "20231201T120000Z"
        assert result.operations == operations
        assert result.dry_run is True


class TestRestoreManager:
    def test_initialization(self):
        client = Mock(org_id="org_123")
        manager = RestoreManager(client, "/backups")

        assert manager.client == client
        assert manager.base_dir == "/backups"

    @patch("meraki_snapshot.restore.list_snapshots")
    def test_available_snapshots(self, mock_list_snapshots):
        mock_list_snapshots.return_value = ["20231201T120000Z", "20231202T130000Z"]

        client = Mock(org_id="org_123")
        manager = RestoreManager(client, "/backups")
        result = manager.available_snapshots()

        assert len(result) == 2
        assert "20231201T120000Z" in result
        mock_list_snapshots.assert_called_once_with("/backups", "org_123")

    def test_snapshot_root(self):
        client = Mock(org_id="org_123")
        manager = RestoreManager(client, "/backups")
        root = manager._snapshot_root("20231201T120000Z")

        assert root == "/backups/org_123/20231201T120000Z"

    @patch("meraki_snapshot.restore.load_network_payloads")
    @patch("meraki_snapshot.restore.read_json")
    def test_load_snapshot(self, mock_read_json, mock_load_networks):
        mock_read_json.return_value = {
            "created_at": "20231201T120000Z",
            "organization": {"id": "org_123", "name": "Test Org"},
        }
        mock_load_networks.return_value = {
            "hq": {"metadata": {"network": {"id": "N_1"}}, "config": {}},
        }

        client = Mock(org_id="org_123")
        manager = RestoreManager(client, "/backups")
        snapshot = manager.load_snapshot("20231201T120000Z")

        assert "index" in snapshot
        assert "networks" in snapshot
        assert "root" in snapshot
        assert snapshot["index"]["organization"]["id"] == "org_123"

    @patch("meraki_snapshot.restore.load_network_payloads")
    @patch("meraki_snapshot.restore.read_json")
    def test_restore_all_networks(self, mock_read_json, mock_load_networks):
        mock_read_json.return_value = {"created_at": "20231201T120000Z"}
        mock_load_networks.return_value = {
            "hq": {
                "metadata": {"network": {"id": "N_1", "name": "HQ"}},
                "config": {"appliance": {"vlans": []}},
            },
            "branch": {
                "metadata": {"network": {"id": "N_2", "name": "Branch"}},
                "config": {"wireless": {"ssids": []}},
            },
        }

        mock_client = Mock(org_id="org_123")
        mock_client.apply_network_config.return_value = ["config applied"]

        manager = RestoreManager(mock_client, "/backups")
        result = manager.restore("20231201T120000Z", dry_run=True)

        assert result.snapshot == "20231201T120000Z"
        assert result.dry_run is True
        assert len(result.operations) == 2
        assert mock_client.apply_network_config.call_count == 2

    @patch("meraki_snapshot.restore.load_network_payloads")
    @patch("meraki_snapshot.restore.read_json")
    def test_restore_filtered_networks(self, mock_read_json, mock_load_networks):
        mock_read_json.return_value = {"created_at": "20231201T120000Z"}
        mock_load_networks.return_value = {
            "hq": {
                "metadata": {"network": {"id": "N_1", "name": "HQ"}},
                "config": {},
            },
            "branch": {
                "metadata": {"network": {"id": "N_2", "name": "Branch"}},
                "config": {},
            },
        }

        mock_client = Mock(org_id="org_123")
        mock_client.apply_network_config.return_value = []

        manager = RestoreManager(mock_client, "/backups")
        result = manager.restore("20231201T120000Z", network_names=["HQ"], dry_run=False)

        assert len(result.operations) == 1
        assert result.operations[0]["network"] == "HQ"
        assert result.dry_run is False

    @patch("meraki_snapshot.restore.load_network_payloads")
    @patch("meraki_snapshot.restore.read_json")
    def test_restore_network_without_name_uses_folder(self, mock_read_json, mock_load_networks):
        mock_read_json.return_value = {"created_at": "20231201T120000Z"}
        mock_load_networks.return_value = {
            "unnamed-network": {
                "metadata": {"network": {"id": "N_1"}},  # No name field
                "config": {},
            },
        }

        mock_client = Mock(org_id="org_123")
        mock_client.apply_network_config.return_value = []

        manager = RestoreManager(mock_client, "/backups")
        result = manager.restore("20231201T120000Z", dry_run=True)

        assert len(result.operations) == 1
        assert result.operations[0]["network"] == "unnamed-network"
