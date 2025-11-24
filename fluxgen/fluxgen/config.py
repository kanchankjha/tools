"""
Configuration loading and merging helpers.
"""

from __future__ import annotations

import json
import pathlib
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class RuntimeConfig:
    interface: str
    dst: str
    clients: int = 1
    subnet_pool: Optional[str] = None
    dest_subnet: Optional[str] = None
    dport: Optional[int] = None
    sport: Optional[int] = None
    proto: str = "tcp"
    flags: str = "S"
    interval: float = 0.1
    count: int = 1
    payload: Optional[str] = None
    payload_hex: bool = False
    flood: bool = False
    rand_source: bool = False
    rand_dest: bool = False
    ttl: int = 64
    tos: int = 0
    ip_id: Optional[int] = None
    frag: bool = False
    frag_size: Optional[int] = None
    icmp_type: int = 8
    icmp_code: int = 0
    dry_run: bool = False
    pcap_out: Optional[str] = None
    verbose: bool = False
    quiet: bool = False
    extra: Dict[str, Any] = field(default_factory=dict)


def load_config_file(path: str) -> Dict[str, Any]:
    """
    Load a JSON or YAML config file. YAML is optional.
    """
    config_path = pathlib.Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    text = config_path.read_text()
    if config_path.suffix.lower() in {".yaml", ".yml"}:
        try:
            import yaml  # type: ignore
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError("pyyaml is required to read YAML configs") from exc

        data = yaml.safe_load(text) or {}
    else:
        data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("Config file must define a mapping at the top level")
    return data


def merge_config(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """
    Combine two config dictionaries, keeping override values when provided.
    """
    merged = dict(base)
    for key, value in override.items():
        if value is None:
            continue
        merged[key] = value
    return merged


def build_runtime_config(data: Dict[str, Any]) -> RuntimeConfig:
    """
    Normalize dictionary input into a RuntimeConfig.
    """
    if "interface" not in data or not data.get("interface"):
        raise ValueError("Missing required option: interface")
    if not data.get("dst") and not data.get("dest_subnet"):
        raise ValueError("Provide dst or dest_subnet to target traffic")

    # Validate ports
    dport = _maybe_int(data.get("dport"))
    if dport is not None and not (0 <= dport <= 65535):
        raise ValueError(f"Invalid destination port: {dport} (must be 0-65535)")
    sport = _maybe_int(data.get("sport"))
    if sport is not None and not (0 <= sport <= 65535):
        raise ValueError(f"Invalid source port: {sport} (must be 0-65535)")

    # Validate TCP flags
    flags = str(data.get("flags", "S") or "S")
    if not _validate_tcp_flags(flags):
        raise ValueError(f"Invalid TCP flags: {flags} (use S,A,F,P,R,U)")

    # Validate ICMP type and code
    icmp_type = _as_int(data.get("icmp_type"), default=8)
    if not (0 <= icmp_type <= 255):
        raise ValueError(f"Invalid ICMP type: {icmp_type} (must be 0-255)")
    icmp_code = _as_int(data.get("icmp_code"), default=0)
    if not (0 <= icmp_code <= 255):
        raise ValueError(f"Invalid ICMP code: {icmp_code} (must be 0-255)")

    # Validate protocol
    proto = str(data.get("proto", "tcp") or "tcp").lower()
    valid_protocols = {"tcp", "udp", "icmp", "igmp", "gre", "esp", "ah", "sctp"}
    if proto not in valid_protocols:
        raise ValueError(f"Invalid protocol: {proto} (must be one of {', '.join(sorted(valid_protocols))})")

    return RuntimeConfig(
        interface=data["interface"],
        dst=str(data.get("dst", "") or ""),
        clients=_as_int(data.get("clients"), default=1),
        subnet_pool=data.get("subnet_pool"),
        dest_subnet=data.get("dest_subnet"),
        dport=dport,
        sport=sport,
        proto=proto,
        flags=flags,
        interval=_as_float(data.get("interval"), default=0.1),
        count=_as_int(data.get("count"), default=1),
        payload=data.get("payload"),
        payload_hex=bool(data.get("payload_hex", False)),
        flood=bool(data.get("flood", False)),
        rand_source=bool(data.get("rand_source", False)),
        rand_dest=bool(data.get("rand_dest", False)),
        ttl=_as_int(data.get("ttl"), default=64),
        tos=_as_int(data.get("tos"), default=0),
        ip_id=_maybe_int(data.get("ip_id")),
        frag=bool(data.get("frag", False)),
        frag_size=_maybe_int(data.get("frag_size")),
        icmp_type=icmp_type,
        icmp_code=icmp_code,
        dry_run=bool(data.get("dry_run", False)),
        pcap_out=data.get("pcap_out"),
        verbose=bool(data.get("verbose", False)),
        quiet=bool(data.get("quiet", False)),
        extra={k: v for k, v in data.items() if k not in _known_keys()},
    )


def _maybe_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _known_keys() -> set:
    return {
        "interface",
        "dst",
        "clients",
        "subnet_pool",
        "dest_subnet",
        "dport",
        "sport",
        "proto",
        "flags",
        "interval",
        "count",
        "payload",
        "payload_hex",
        "flood",
        "rand_source",
        "rand_dest",
        "ttl",
        "tos",
        "ip_id",
        "frag",
        "frag_size",
        "icmp_type",
        "icmp_code",
        "dry_run",
        "pcap_out",
        "verbose",
        "quiet",
    }


def _as_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _validate_tcp_flags(flags: str) -> bool:
    """
    Validate TCP flags string. Accepts hping3-style flags: S,A,F,P,R,U.
    """
    valid_flags = set("SAFPRU")
    return all(c in valid_flags for c in flags.upper())
