"""
Packet construction helpers that mimic common hping3 flags.
"""

from __future__ import annotations

import os
import random
from typing import List, Sequence

from scapy.all import (  # type: ignore
    Ether,
    ICMP,
    IP,
    TCP,
    UDP,
    RandShort,
    Raw,
    fragment,
)

from .config import RuntimeConfig
from .identity import Identity


def build_frames(
    cfg: RuntimeConfig,
    identity: Identity,
    dest_ip: str,
    dest_mac: str,
) -> List:
    """
    Build one or more Ethernet frames for a single send.
    """
    ip_layer = IP(
        src=str(identity.ip),
        dst=dest_ip,
        ttl=cfg.ttl,
        tos=cfg.tos,
    )
    if cfg.ip_id is not None:
        ip_layer.id = cfg.ip_id

    payload = _build_payload(cfg)

    if cfg.proto == "tcp":
        transport = TCP(
            sport=cfg.sport or RandShort(),
            dport=cfg.dport or 0,
            flags=cfg.flags,
            seq=random.randint(0, 2**32 - 1),
            ack=0,
        )
    elif cfg.proto == "udp":
        transport = UDP(
            sport=cfg.sport or RandShort(),
            dport=cfg.dport or 0,
        )
    elif cfg.proto == "icmp":
        transport = ICMP(type=cfg.icmp_type, code=cfg.icmp_code)
    else:
        raise ValueError(f"Unsupported protocol: {cfg.proto}")

    ether = Ether(src=identity.mac, dst=dest_mac)
    base_pkt = ether / ip_layer / transport
    if payload:
        base_pkt = base_pkt / payload

    if cfg.frag:
        fragments = fragment(base_pkt[IP], fragsize=cfg.frag_size or 1480)
        return [ether / frag for frag in fragments]
    return [base_pkt]


def _build_payload(cfg: RuntimeConfig) -> Raw | None:
    if cfg.payload is None:
        return None
    data = cfg.payload
    if cfg.payload_hex:
        try:
            data_bytes = bytes.fromhex(data.replace(" ", ""))
        except ValueError as exc:
            raise ValueError("payload must be hex when payload_hex=true") from exc
    else:
        data_bytes = data.encode("utf-8")
    if not data_bytes:
        return None
    return Raw(load=data_bytes)
