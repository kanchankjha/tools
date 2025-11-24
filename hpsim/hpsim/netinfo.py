"""
Network interface discovery helpers.
"""

from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from typing import Optional

import psutil


@dataclass
class InterfaceInfo:
    name: str
    address: ipaddress.IPv4Interface
    mac: str
    gateway: Optional[str]


def get_interface_info(name: str) -> InterfaceInfo:
    addrs = psutil.net_if_addrs().get(name)
    if not addrs:
        raise ValueError(f"Interface not found: {name}")

    ipv4_addr = None
    mac_addr = None
    for addr in addrs:
        if addr.family == socket.AF_INET and addr.address:
            ipv4_addr = ipaddress.ip_interface(f"{addr.address}/{addr.netmask}")
        elif addr.family == psutil.AF_LINK and addr.address:
            mac_addr = addr.address

    if ipv4_addr is None:
        raise ValueError(f"Interface {name} does not have an IPv4 address")
    if mac_addr is None:
        raise ValueError(f"Interface {name} does not have a MAC address")

    gateway = _default_gateway(name)
    return InterfaceInfo(name=name, address=ipv4_addr, mac=mac_addr, gateway=gateway)


def _default_gateway(iface: str) -> Optional[str]:
    try:
        import netifaces  # type: ignore
    except ImportError:  # pragma: no cover - optional dependency
        return None

    gateways = netifaces.gateways()
    default_v4 = gateways.get("default", {}).get(netifaces.AF_INET)
    if not default_v4:
        return None
    gw_ip, gw_iface = default_v4[0], default_v4[1]
    if gw_iface != iface:
        return None
    return gw_ip
