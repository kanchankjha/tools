#!/usr/bin/env python3
"""
Command line helper around the lightweight Meraki dashboard client.

All commands require a Dashboard API key and the target organization ID.
Credentials can be provided via CLI flags, a JSON config file, or environment
variables for flexible automation.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Tuple

# Ensure the project root is importable when executing this file directly.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from lib.meraki_client import MerakiAPIError, MerakiClient


def configure_logging(verbosity: int) -> None:
    level = logging.WARNING
    if verbosity == 1:
        level = logging.INFO
    elif verbosity >= 2:
        level = logging.DEBUG

    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def add_common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--config",
        help="Path to a JSON config file containing api_key/org_id (defaults to ~/.config/meraki/config.json)",
    )
    parser.add_argument(
        "--api-key",
        help="Dashboard API key (falls back to config file or MERAKI_API_KEY env var)",
    )
    parser.add_argument(
        "--org-id",
        help="Organization ID (falls back to config file or MERAKI_ORG_ID env var)",
    )
    parser.add_argument(
        "--base-url",
        default=None,
        help="Override the Meraki Dashboard base URL (rarely needed)",
    )
    parser.add_argument(
        "-v",
        "--verbosity",
        action="count",
        default=0,
        help="Increase logging verbosity (-vv for debug level)",
    )


def create_parser() -> Tuple[argparse.ArgumentParser, argparse._SubParsersAction]:
    parser = argparse.ArgumentParser(
        description="Automate basic Meraki dashboard CRUD workflows.",
    )
    add_common_arguments(parser)
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("list-networks", help="List networks in the organization")

    get_network = subparsers.add_parser("get-network", help="Fetch a specific network")
    get_network.add_argument("network_id", help="The network identifier")

    create_network = subparsers.add_parser("create-network", help="Create a new network")
    create_network.add_argument("--name", required=True, help="Display name for the network")
    create_network.add_argument(
        "--product-types",
        nargs="+",
        required=True,
        help="One or more product types (e.g. MX MS MR)",
    )
    create_network.add_argument(
        "--tags",
        nargs="*",
        help="Optional network tags",
    )
    create_network.add_argument("--timezone", help="Optional timezone (e.g. Europe/Paris)")
    create_network.add_argument("--notes", help="Optional notes/description")

    update_network = subparsers.add_parser("update-network", help="Update an existing network")
    update_network.add_argument("network_id", help="The network identifier")
    update_network.add_argument(
        "--set",
        dest="updates",
        metavar="key=value",
        action="append",
        help="Key/value pairs to update (can be provided multiple times)",
    )

    delete_network = subparsers.add_parser("delete-network", help="Delete a network")
    delete_network.add_argument("network_id", help="The network identifier to remove")

    list_devices = subparsers.add_parser("list-devices", help="List devices claimed in a network")
    list_devices.add_argument("network_id", help="Target network identifier")

    claim_devices = subparsers.add_parser("claim-devices", help="Claim device serials into a network")
    claim_devices.add_argument("network_id", help="Target network identifier")
    claim_devices.add_argument("serials", nargs="+", help="Device serial numbers to claim")

    remove_devices = subparsers.add_parser("remove-devices", help="Remove devices from a network")
    remove_devices.add_argument("network_id", help="Target network identifier")
    remove_devices.add_argument("serials", nargs="+", help="Device serial numbers to remove")

    return parser, subparsers


def parse_updates(pairs: Iterable[str]) -> Dict[str, Any]:
    updates: Dict[str, Any] = {}
    for pair in pairs:
        if "=" not in pair:
            raise ValueError(f"Invalid update '{pair}', expected key=value")
        key, value = pair.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            raise ValueError(f"Invalid update '{pair}', missing key name")
        try:
            updates[key] = json.loads(value)
        except json.JSONDecodeError:
            updates[key] = value
    return updates


def pretty_print(data: Any) -> None:
    if data is None:
        return
    if isinstance(data, str):
        print(data)
        return
    print(json.dumps(data, indent=2, sort_keys=True))


def find_default_config() -> Optional[Path]:
    candidates = [
        Path("~/.config/meraki/config.json").expanduser(),
        Path("~/.meraki_config.json").expanduser(),
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def load_config(path: Optional[str]) -> Dict[str, Any]:
    config_path: Optional[Path] = Path(path).expanduser() if path else find_default_config()
    if not config_path:
        return {}
    try:
        with config_path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
            if not isinstance(data, dict):
                raise ValueError("Configuration file must contain a JSON object")
            return data
    except FileNotFoundError:
        raise SystemExit(f"Config file not found: {config_path}")
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Failed to parse JSON config {config_path}: {exc}") from exc


def resolve_credentials(args: argparse.Namespace) -> Tuple[str, str, str]:
    config = load_config(args.config)
    env_api_key = os.getenv("MERAKI_API_KEY")
    env_org_id = os.getenv("MERAKI_ORG_ID")
    env_base_url = os.getenv("MERAKI_BASE_URL", "https://api.meraki.com/api/v1")

    api_key = args.api_key or config.get("api_key") or env_api_key
    org_id = args.org_id or config.get("org_id") or env_org_id
    base_url = args.base_url or config.get("base_url") or env_base_url

    if not api_key:
        raise SystemExit("A Meraki API key is required (use --api-key, config file, or MERAKI_API_KEY)")
    if not org_id:
        raise SystemExit("An organization ID is required (use --org-id, config file, or MERAKI_ORG_ID)")

    return api_key, org_id, base_url


def main(argv: Iterable[str] | None = None) -> int:
    parser, _ = create_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help(sys.stderr)
        return 2

    api_key, org_id, base_url = resolve_credentials(args)

    configure_logging(args.verbosity)

    client = MerakiClient(
        api_key,
        org_id,
        base_url=base_url,
    )

    try:
        if args.command == "list-networks":
            pretty_print(client.list_networks())
        elif args.command == "get-network":
            pretty_print(client.get_network(args.network_id))
        elif args.command == "create-network":
            pretty_print(
                client.create_network(
                    name=args.name,
                    product_types=args.product_types,
                    tags=args.tags,
                    timezone=args.timezone,
                    notes=args.notes,
                )
            )
        elif args.command == "update-network":
            if not args.updates:
                parser.error("update-network requires at least one --set key=value pair")
            updates = parse_updates(args.updates)
            pretty_print(client.update_network(args.network_id, **updates))
        elif args.command == "delete-network":
            client.delete_network(args.network_id)
            print(f"Network {args.network_id} deleted")
        elif args.command == "list-devices":
            pretty_print(client.list_devices(args.network_id))
        elif args.command == "claim-devices":
            pretty_print(client.claim_devices(args.network_id, args.serials))
        elif args.command == "remove-devices":
            client.remove_devices(args.network_id, args.serials)
            print("Devices removed")
        else:
            parser.error(f"Unknown command '{args.command}'")
    except MerakiAPIError as exc:
        logging.error("Meraki API request failed: %s", exc)
        return 1
    except ValueError as exc:
        logging.error("Invalid parameters: %s", exc)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())

