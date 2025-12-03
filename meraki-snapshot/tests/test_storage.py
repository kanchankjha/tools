import json
import os
from pathlib import Path

import pytest

from meraki_snapshot.storage import (
    ensure_dir,
    list_snapshots,
    load_network_payloads,
    read_json,
    slugify,
    timestamp,
    write_json,
    SnapshotWriter,
)


class TestStorageHelpers:
    def test_timestamp_format(self):
        ts = timestamp()
        assert len(ts) == 16  # YYYYMMDDTHHMMSSz format
        assert ts[8] == "T"
        assert ts.endswith("Z")

    def test_slugify_basic(self):
        assert slugify("My Network") == "my-network"
        assert slugify("HQ-Office") == "hq-office"
        assert slugify("Branch_1") == "branch-1"

    def test_slugify_special_chars(self):
        assert slugify("Test@#$%Network") == "test-network"
        assert slugify("   spaced   ") == "spaced"
        assert slugify("UPPERCASE") == "uppercase"

    def test_slugify_empty(self):
        assert slugify("") == "network"
        assert slugify("@#$%") == "network"

    def test_ensure_dir_creates_directory(self, tmp_path):
        test_dir = tmp_path / "test" / "nested" / "dir"
        ensure_dir(str(test_dir))
        assert test_dir.exists()
        assert test_dir.is_dir()

    def test_ensure_dir_existing_directory(self, tmp_path):
        test_dir = tmp_path / "existing"
        test_dir.mkdir()
        ensure_dir(str(test_dir))  # Should not raise
        assert test_dir.exists()

    def test_write_and_read_json(self, tmp_path):
        test_file = tmp_path / "test.json"
        test_data = {"key": "value", "number": 42, "nested": {"inner": True}}

        write_json(str(test_file), test_data)

        assert test_file.exists()
        result = read_json(str(test_file))
        assert result == test_data

    def test_write_json_creates_parent_dirs(self, tmp_path):
        test_file = tmp_path / "deep" / "nested" / "path" / "data.json"
        test_data = {"test": True}

        write_json(str(test_file), test_data)

        assert test_file.exists()
        result = read_json(str(test_file))
        assert result["test"] is True

    def test_list_snapshots_empty(self, tmp_path):
        result = list_snapshots(str(tmp_path), "org_123")
        assert result == []

    def test_list_snapshots_with_data(self, tmp_path):
        org_dir = tmp_path / "org_123"
        org_dir.mkdir()
        (org_dir / "20231201T120000Z").mkdir()
        (org_dir / "20231202T130000Z").mkdir()
        (org_dir / "file.txt").touch()  # Should be ignored

        result = list_snapshots(str(tmp_path), "org_123")

        assert len(result) == 2
        assert "20231201T120000Z" in result
        assert "20231202T130000Z" in result
        assert result == sorted(result)  # Should be sorted

    def test_load_network_payloads(self, tmp_path):
        snapshot_dir = tmp_path / "snapshot"
        snapshot_dir.mkdir()

        # Create network folders
        net1 = snapshot_dir / "hq"
        net1.mkdir()
        write_json(str(net1 / "metadata.json"), {"network": {"id": "N_1", "name": "HQ"}})
        write_json(str(net1 / "config.json"), {"appliance": {"vlans": []}})

        net2 = snapshot_dir / "branch"
        net2.mkdir()
        write_json(str(net2 / "metadata.json"), {"network": {"id": "N_2", "name": "Branch"}})
        write_json(str(net2 / "config.json"), {"wireless": {"ssids": []}})

        # Create a file that should be ignored
        (snapshot_dir / "index.json").touch()

        result = load_network_payloads(str(snapshot_dir))

        assert len(result) == 2
        assert "hq" in result
        assert "branch" in result
        assert result["hq"]["metadata"]["network"]["name"] == "HQ"
        assert "config" in result["hq"]

    def test_load_network_payloads_incomplete_folder(self, tmp_path):
        snapshot_dir = tmp_path / "snapshot"
        snapshot_dir.mkdir()

        # Create incomplete network folder (missing config.json)
        net1 = snapshot_dir / "incomplete"
        net1.mkdir()
        write_json(str(net1 / "metadata.json"), {"network": {"id": "N_1"}})

        result = load_network_payloads(str(snapshot_dir))

        assert len(result) == 0  # Should skip incomplete folders


class TestSnapshotWriter:
    def test_initialization(self, tmp_path):
        writer = SnapshotWriter(str(tmp_path), "org_123")

        assert writer.base_dir == str(tmp_path)
        assert writer.org_id == "org_123"
        assert writer.snap_ts is not None
        assert Path(writer.root).exists()
        assert "org_123" in writer.root

    def test_initialization_with_custom_timestamp(self, tmp_path):
        custom_ts = "20231201T120000Z"
        writer = SnapshotWriter(str(tmp_path), "org_123", snap_ts=custom_ts)

        assert writer.snap_ts == custom_ts
        assert custom_ts in writer.root

    def test_index_path(self, tmp_path):
        writer = SnapshotWriter(str(tmp_path), "org_123")
        index_path = writer.index_path()

        assert index_path.endswith("index.json")
        assert writer.root in index_path

    def test_write_index(self, tmp_path):
        writer = SnapshotWriter(str(tmp_path), "org_123")
        index_data = {
            "created_at": writer.snap_ts,
            "organization": {"id": "org_123", "name": "Test Org"},
            "networks": [],
        }

        path = writer.write_index(index_data)

        assert Path(path).exists()
        loaded_data = read_json(path)
        assert loaded_data["organization"]["id"] == "org_123"

    def test_network_paths(self, tmp_path):
        writer = SnapshotWriter(str(tmp_path), "org_123")
        metadata_path, config_path = writer.network_paths("HQ Office")

        assert "hq-office" in metadata_path
        assert metadata_path.endswith("metadata.json")
        assert config_path.endswith("config.json")
        assert Path(metadata_path).parent == Path(config_path).parent

    def test_write_network(self, tmp_path):
        writer = SnapshotWriter(str(tmp_path), "org_123")
        network_data = {"id": "N_1", "name": "HQ Office", "productTypes": ["appliance"]}
        devices_data = [{"serial": "Q2XX-1234", "model": "MX68"}]
        config_data = {"appliance": {"vlans": [{"id": 1, "name": "Default"}]}}

        writer.write_network(network_data, devices_data, config_data)

        metadata_path, config_path = writer.network_paths("HQ Office")
        assert Path(metadata_path).exists()
        assert Path(config_path).exists()

        metadata = read_json(metadata_path)
        assert metadata["network"]["id"] == "N_1"
        assert len(metadata["devices"]) == 1

        config = read_json(config_path)
        assert "appliance" in config

    def test_write_network_with_missing_name(self, tmp_path):
        writer = SnapshotWriter(str(tmp_path), "org_123")
        network_data = {"id": "N_1"}  # No name

        writer.write_network(network_data, [], {})

        # Should use network ID as fallback
        metadata_path, _ = writer.network_paths("N_1")
        assert Path(metadata_path).exists()

    def test_multiple_snapshots(self, tmp_path):
        writer1 = SnapshotWriter(str(tmp_path), "org_123", snap_ts="20231201T120000Z")
        writer2 = SnapshotWriter(str(tmp_path), "org_123", snap_ts="20231202T130000Z")

        writer1.write_index({"test": 1})
        writer2.write_index({"test": 2})

        snapshots = list_snapshots(str(tmp_path), "org_123")
        assert len(snapshots) == 2
        assert "20231201T120000Z" in snapshots
        assert "20231202T130000Z" in snapshots
