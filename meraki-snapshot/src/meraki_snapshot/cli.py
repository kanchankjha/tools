import argparse
import os
import sys
from typing import List, Optional

from meraki_snapshot.backup import BackupManager
from meraki_snapshot.client import MerakiClient
from meraki_snapshot.restore import RestoreManager


def build_client(args: argparse.Namespace) -> MerakiClient:
    api_key = args.api_key or os.getenv("MERAKI_API_KEY")
    if not api_key:
        print("API key must be provided via --api-key or MERAKI_API_KEY", file=sys.stderr)
        sys.exit(1)
    if not args.org_id:
        print("--org-id is required", file=sys.stderr)
        sys.exit(1)
    return MerakiClient(api_key=api_key, org_id=args.org_id, base_url=args.base_url)


def command_backup(args: argparse.Namespace) -> None:
    client = build_client(args)
    mgr = BackupManager(client, args.output)
    summary = mgr.snapshot()
    print(f"Backup complete: {summary.root}")
    for net in summary.networks:
        print(f"- {net['name']} ({net['id']}) -> {net['folder']}")


def command_list(args: argparse.Namespace) -> None:
    client = build_client(args)
    mgr = RestoreManager(client, args.output)
    snapshots = mgr.available_snapshots()
    if not snapshots:
        print("No snapshots found.")
        return
    print("Available snapshots:")
    for snap in snapshots:
        print(f"- {snap}")


def command_restore(args: argparse.Namespace) -> None:
    client = build_client(args)
    mgr = RestoreManager(client, args.output)
    network_names: Optional[List[str]] = args.networks if args.networks else None
    result = mgr.restore(args.from_backup, network_names=network_names, dry_run=args.dry_run)
    print(f"Snapshot: {result.snapshot}")
    print("Dry run" if result.dry_run else "Applying configuration")
    for op in result.operations:
        print(f"- {op['network']}: {', '.join(op['operations']) if op['operations'] else 'no changes planned'}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="meraki-snapshot", description="Backup and restore Meraki Dashboard configs.")
    parser.add_argument("--api-key", help="Meraki Dashboard API key (or set MERAKI_API_KEY).")
    parser.add_argument("--org-id", help="Organization ID to operate on.")
    parser.add_argument("--base-url", default="https://api.meraki.com/api/v1", help="Override Meraki base URL.")
    parser.add_argument("--output", default="backups", help="Directory to store backups.")

    subparsers = parser.add_subparsers(dest="command", required=True)

    backup = subparsers.add_parser("backup", help="Run a new backup.")
    backup.set_defaults(func=command_backup)

    list_cmd = subparsers.add_parser("list", help="List available backups.")
    list_cmd.set_defaults(func=command_list)

    restore = subparsers.add_parser("restore", help="Restore from a backup (dry-run by default).")
    restore.add_argument("--from-backup", required=True, help="Timestamp folder to restore from.")
    restore.add_argument("--networks", nargs="*", help="Network names to restore; default restores all.")
    restore.add_argument("--dry-run", action="store_true", default=True, help="Preview operations without applying.")
    restore.set_defaults(func=command_restore)

    return parser


def main(argv: Optional[List[str]] = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
