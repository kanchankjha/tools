import os
import sys
from io import StringIO
from unittest.mock import Mock, patch

import pytest

from meraki_snapshot.cli import (
    build_client,
    build_parser,
    command_backup,
    command_list,
    command_restore,
    main,
)
from meraki_snapshot.client import MerakiClient


class TestBuildClient:
    def test_build_client_with_api_key_arg(self):
        args = Mock(api_key="test_key", org_id="org_123", base_url="https://api.meraki.com/api/v1")
        client = build_client(args)

        assert isinstance(client, MerakiClient)
        assert client.api_key == "test_key"
        assert client.org_id == "org_123"

    def test_build_client_with_env_var(self, monkeypatch):
        monkeypatch.setenv("MERAKI_API_KEY", "env_key")
        args = Mock(api_key=None, org_id="org_123", base_url="https://api.meraki.com/api/v1")
        client = build_client(args)

        assert client.api_key == "env_key"

    def test_build_client_no_api_key(self, capsys):
        args = Mock(api_key=None, org_id="org_123", base_url="https://api.meraki.com/api/v1")

        with pytest.raises(SystemExit) as exc_info:
            build_client(args)

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "API key must be provided" in captured.err

    def test_build_client_no_org_id(self, capsys):
        args = Mock(api_key="test_key", org_id=None, base_url="https://api.meraki.com/api/v1")

        with pytest.raises(SystemExit) as exc_info:
            build_client(args)

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "--org-id is required" in captured.err


class TestCommandBackup:
    @patch("meraki_snapshot.cli.build_client")
    @patch("meraki_snapshot.cli.BackupManager")
    def test_command_backup(self, mock_manager_class, mock_build_client, capsys):
        mock_client = Mock()
        mock_build_client.return_value = mock_client

        mock_manager = Mock()
        mock_summary = Mock()
        mock_summary.root = "/backups/org_123/20231201T120000Z"
        mock_summary.networks = [
            {"name": "HQ", "id": "N_1", "folder": "hq"},
            {"name": "Branch", "id": "N_2", "folder": "branch"},
        ]
        mock_manager.snapshot.return_value = mock_summary
        mock_manager_class.return_value = mock_manager

        args = Mock(output="/backups", api_key="test", org_id="org_123", base_url="https://api.meraki.com/api/v1")
        command_backup(args)

        captured = capsys.readouterr()
        assert "Backup complete" in captured.out
        assert "HQ" in captured.out
        assert "Branch" in captured.out


class TestCommandList:
    @patch("meraki_snapshot.cli.build_client")
    @patch("meraki_snapshot.cli.RestoreManager")
    def test_command_list_with_snapshots(self, mock_manager_class, mock_build_client, capsys):
        mock_client = Mock()
        mock_build_client.return_value = mock_client

        mock_manager = Mock()
        mock_manager.available_snapshots.return_value = ["20231201T120000Z", "20231202T130000Z"]
        mock_manager_class.return_value = mock_manager

        args = Mock(output="/backups", api_key="test", org_id="org_123", base_url="https://api.meraki.com/api/v1")
        command_list(args)

        captured = capsys.readouterr()
        assert "Available snapshots" in captured.out
        assert "20231201T120000Z" in captured.out
        assert "20231202T130000Z" in captured.out

    @patch("meraki_snapshot.cli.build_client")
    @patch("meraki_snapshot.cli.RestoreManager")
    def test_command_list_no_snapshots(self, mock_manager_class, mock_build_client, capsys):
        mock_client = Mock()
        mock_build_client.return_value = mock_client

        mock_manager = Mock()
        mock_manager.available_snapshots.return_value = []
        mock_manager_class.return_value = mock_manager

        args = Mock(output="/backups", api_key="test", org_id="org_123", base_url="https://api.meraki.com/api/v1")
        command_list(args)

        captured = capsys.readouterr()
        assert "No snapshots found" in captured.out


class TestCommandRestore:
    @patch("meraki_snapshot.cli.build_client")
    @patch("meraki_snapshot.cli.RestoreManager")
    def test_command_restore_dry_run(self, mock_manager_class, mock_build_client, capsys):
        mock_client = Mock()
        mock_build_client.return_value = mock_client

        mock_manager = Mock()
        mock_result = Mock()
        mock_result.snapshot = "20231201T120000Z"
        mock_result.dry_run = True
        mock_result.operations = [
            {"network": "HQ", "operations": ["appliance.vlans planned"]},
            {"network": "Branch", "operations": []},
        ]
        mock_manager.restore.return_value = mock_result
        mock_manager_class.return_value = mock_manager

        args = Mock(
            output="/backups",
            from_backup="20231201T120000Z",
            networks=None,
            dry_run=True,
            api_key="test",
            org_id="org_123",
            base_url="https://api.meraki.com/api/v1",
        )
        command_restore(args)

        captured = capsys.readouterr()
        assert "Dry run" in captured.out
        assert "HQ" in captured.out

    @patch("meraki_snapshot.cli.build_client")
    @patch("meraki_snapshot.cli.RestoreManager")
    def test_command_restore_with_network_filter(self, mock_manager_class, mock_build_client):
        mock_client = Mock()
        mock_build_client.return_value = mock_client

        mock_manager = Mock()
        mock_result = Mock()
        mock_result.snapshot = "20231201T120000Z"
        mock_result.dry_run = False
        mock_result.operations = [{"network": "HQ", "operations": ["config applied"]}]
        mock_manager.restore.return_value = mock_result
        mock_manager_class.return_value = mock_manager

        args = Mock(
            output="/backups",
            from_backup="20231201T120000Z",
            networks=["HQ"],
            dry_run=False,
            api_key="test",
            org_id="org_123",
            base_url="https://api.meraki.com/api/v1",
        )
        command_restore(args)

        mock_manager.restore.assert_called_once_with("20231201T120000Z", network_names=["HQ"], dry_run=False)


class TestBuildParser:
    def test_parser_backup_command(self):
        parser = build_parser()
        args = parser.parse_args(["--api-key", "test", "--org-id", "123", "backup"])

        assert args.command == "backup"
        assert args.api_key == "test"
        assert args.org_id == "123"

    def test_parser_list_command(self):
        parser = build_parser()
        args = parser.parse_args(["--org-id", "123", "list"])

        assert args.command == "list"

    def test_parser_restore_command(self):
        parser = build_parser()
        args = parser.parse_args([
            "--org-id", "123",
            "restore",
            "--from-backup", "20231201T120000Z",
            "--networks", "HQ", "Branch",
        ])

        assert args.command == "restore"
        assert args.from_backup == "20231201T120000Z"
        assert args.networks == ["HQ", "Branch"]
        assert args.dry_run is True  # default

    def test_parser_custom_base_url(self):
        parser = build_parser()
        args = parser.parse_args([
            "--org-id", "123",
            "--base-url", "https://api.meraki.com/api/v1",
            "backup",
        ])

        assert args.base_url == "https://api.meraki.com/api/v1"

    def test_parser_custom_output_dir(self):
        parser = build_parser()
        args = parser.parse_args(["--org-id", "123", "--output", "/custom/path", "backup"])

        assert args.output == "/custom/path"

    def test_parser_requires_command(self):
        parser = build_parser()

        with pytest.raises(SystemExit):
            parser.parse_args(["--org-id", "123"])


class TestMain:
    @patch("meraki_snapshot.cli.build_client")
    @patch("meraki_snapshot.cli.BackupManager")
    def test_main_backup(self, mock_manager_class, mock_build_client, capsys):
        mock_client = Mock()
        mock_build_client.return_value = mock_client

        mock_manager = Mock()
        mock_summary = Mock()
        mock_summary.root = "/backups/org_123/20231201T120000Z"
        mock_summary.networks = []
        mock_manager.snapshot.return_value = mock_summary
        mock_manager_class.return_value = mock_manager

        main(["--api-key", "test", "--org-id", "123", "backup"])

        captured = capsys.readouterr()
        assert "Backup complete" in captured.out

    @patch("meraki_snapshot.cli.build_client")
    @patch("meraki_snapshot.cli.RestoreManager")
    def test_main_list(self, mock_manager_class, mock_build_client, capsys):
        mock_client = Mock()
        mock_build_client.return_value = mock_client

        mock_manager = Mock()
        mock_manager.available_snapshots.return_value = []
        mock_manager_class.return_value = mock_manager

        main(["--api-key", "test", "--org-id", "123", "list"])

        captured = capsys.readouterr()
        assert "No snapshots found" in captured.out

    @patch("meraki_snapshot.cli.build_client")
    @patch("meraki_snapshot.cli.RestoreManager")
    def test_main_restore(self, mock_manager_class, mock_build_client, capsys):
        mock_client = Mock()
        mock_build_client.return_value = mock_client

        mock_manager = Mock()
        mock_result = Mock()
        mock_result.snapshot = "20231201T120000Z"
        mock_result.dry_run = True
        mock_result.operations = []
        mock_manager.restore.return_value = mock_result
        mock_manager_class.return_value = mock_manager

        main(["--api-key", "test", "--org-id", "123", "restore", "--from-backup", "20231201T120000Z"])

        captured = capsys.readouterr()
        assert "Dry run" in captured.out

    def test_main_no_args(self):
        """Test main with no arguments defaults to sys.argv"""
        with pytest.raises(SystemExit):
            main([])


    def test_main_with_no_argv_uses_sysargv(self, monkeypatch):
        """Test that main() without arguments uses sys.argv"""
        mock_client = Mock()
        mock_manager = Mock()
        mock_summary = Mock()
        mock_summary.root = "/backups/org_123/20231201T120000Z"
        mock_summary.networks = []
        mock_manager.snapshot.return_value = mock_summary

        with patch("meraki_snapshot.cli.build_client", return_value=mock_client):
            with patch("meraki_snapshot.cli.BackupManager", return_value=mock_manager):
                monkeypatch.setattr(sys, "argv", ["prog", "--api-key", "test", "--org-id", "123", "backup"])
                main()  # Call without arguments to use sys.argv
                assert mock_manager.snapshot.called
