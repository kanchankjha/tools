"""
Identity pool generation for simulated clients.
"""

from __future__ import annotations

import ipaddress
import random
from dataclasses import dataclass
from typing import Iterable, List, Optional, Set


@dataclass
class Identity:
    ip: ipaddress.IPv4Address
    mac: str


def generate_identities(
    count: int,
    network: ipaddress.IPv4Network,
    exclude_ips: Iterable[str],
    base_mac: Optional[str] = None,
) -> List[Identity]:
    excluded: Set[str] = {str(ip) for ip in exclude_ips}
    hosts = [ip for ip in network.hosts() if str(ip) not in excluded]
    if len(hosts) < count:
        raise ValueError(f"Not enough usable IPs in {network} to allocate {count} clients")

    mac_seed = _mac_seed(base_mac)
    identities: List[Identity] = []
    for idx in range(count):
        mac = _mac_from_seed(mac_seed, idx)
        identities.append(Identity(ip=hosts[idx], mac=mac))
    return identities


def _mac_seed(base_mac: Optional[str]) -> List[int]:
    """
    Generate a MAC address seed for creating sequential addresses.

    If base_mac is provided, use it as the seed. Otherwise, generate
    a locally administered MAC with prefix 02:00:00 (the 0x02 prefix
    indicates a locally administered address, not globally unique).

    Args:
        base_mac: Optional MAC address string in format "xx:xx:xx:xx:xx:xx"

    Returns:
        List of 6 integers representing MAC bytes
    """
    if base_mac:
        try:
            parts = [int(part, 16) for part in base_mac.split(":")]
            if len(parts) != 6:
                raise ValueError
            return parts
        except ValueError as exc:
            raise ValueError(f"Invalid MAC address: {base_mac}") from exc

    # Locally administered prefix 02:00:00 with random tail
    # The 0x02 bit indicates this is not a globally unique MAC
    return [0x02, 0x00, 0x00, random.randint(0, 255), random.randint(0, 255), 0x00]


def _mac_from_seed(seed: List[int], index: int) -> str:
    """
    Generate a MAC address by incrementing the seed by index.

    Args:
        seed: Base MAC address as list of 6 bytes
        index: Offset to add to base MAC (0-based)

    Returns:
        MAC address string in format "xx:xx:xx:xx:xx:xx"
    """
    mac_bytes = seed[:]
    mac_int = 0
    for byte in mac_bytes:
        mac_int = (mac_int << 8) | byte
    mac_int = (mac_int + index + 1) % (1 << 48)
    mac = mac_int.to_bytes(6, "big")
    return ":".join(f"{byte:02x}" for byte in mac)
