import argparse
import json
import logging
import pathlib
import sys
from typing import Any, Dict

import yaml

from .manager import AppConfig, Controller


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plan multi-session AnyConnect/OpenConnect pods.")
    parser.add_argument(
        "--config",
        type=pathlib.Path,
        default=pathlib.Path("config.yaml"),
        help="Path to config YAML (default: config.yaml)",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Log level (default: INFO)",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("launch", help="Plan creation of VPN pods")
    subparsers.add_parser("status", help="Show planned leases")

    destroy_parser = subparsers.add_parser("destroy", help="Plan teardown for pods")
    destroy_parser.add_argument(
        "--pods",
        nargs="*",
        help="Specific pods to destroy (default: all planned pods)",
    )

    return parser.parse_args(argv)


def load_config(path: pathlib.Path) -> AppConfig:
    if not path.exists():
        raise FileNotFoundError(f"Config not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        data: Dict[str, Any] = yaml.safe_load(handle) or {}
    return AppConfig.from_dict(data)


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    configure_logging(args.log_level)

    try:
        config = load_config(args.config)
    except Exception as exc:  # broad catch to surface config issues to users
        logging.error("Failed to load config: %s", exc)
        return 1

    controller = Controller(config)

    if args.command == "launch":
        plan = controller.launch()
        print(json.dumps(plan, indent=2))
        print("# Commands are not executed in scaffold mode; run manually or wire executor.")
        return 0

    if args.command == "status":
        print(json.dumps(controller.status(), indent=2))
        return 0

    if args.command == "destroy":
        teardown = controller.destroy(pods=args.pods)
        print(json.dumps(teardown, indent=2))
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
