"""
Packet sending orchestration and client simulation.
"""

from __future__ import annotations

import ipaddress
import random
import threading
import time
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

from scapy.all import PcapWriter, sendp  # type: ignore
from scapy.layers.l2 import getmacbyip  # type: ignore

from .config import RuntimeConfig
from .identity import Identity, generate_identities
from .netinfo import get_interface_info
from .packet_builder import build_frames


@dataclass
class SendStats:
    sent: int = 0
    errors: int = 0

    def bump_sent(self, count: int = 1) -> None:
        self.sent += count

    def bump_error(self, count: int = 1) -> None:
        self.errors += count


class Simulator:
    def __init__(self, cfg: RuntimeConfig):
        self.cfg = cfg
        self.stop_event = threading.Event()
        self.stats = SendStats()
        self.dest_mac_cache: Dict[str, str] = {}
        self.identities: List[Identity] = []
        self.writer: Optional[PcapWriter] = None

    def run(self) -> SendStats:
        iface_info = get_interface_info(self.cfg.interface)
        network = (
            ipaddress.ip_network(self.cfg.subnet_pool, strict=False)
            if self.cfg.subnet_pool
            else iface_info.address.network
        )
        excludes: List[str] = [str(iface_info.address.ip)]
        if iface_info.gateway:
            excludes.append(iface_info.gateway)

        self.identities = generate_identities(
            count=self.cfg.clients,
            network=network,
            exclude_ips=excludes,
            base_mac=iface_info.mac,
        )

        dest_pool = _build_dest_pool(self.cfg)
        if not dest_pool:
            raise ValueError("No destination IPs available to target")

        if self.cfg.pcap_out:
            self.writer = PcapWriter(self.cfg.pcap_out, append=True, sync=True)

        workers = [
            threading.Thread(
                target=self._client_loop,
                args=(identity, dest_pool),
                daemon=True,
                name=f"client-{idx}",
            )
            for idx, identity in enumerate(self.identities)
        ]
        reporter = threading.Thread(target=self._report_loop, daemon=True, name="stats")

        reporter.start()
        for worker in workers:
            worker.start()

        try:
            for worker in workers:
                worker.join()
        except KeyboardInterrupt:
            self.stop_event.set()
            for worker in workers:
                worker.join()
        finally:
            if self.writer:
                self.writer.close()
        self.stop_event.set()
        return self.stats

    def _client_loop(self, identity: Identity, dest_pool: List[str]) -> None:
        count_limit = self.cfg.count if self.cfg.count > 0 else None
        sends = 0
        while not self.stop_event.is_set():
            dest_ip = random.choice(dest_pool) if self.cfg.rand_dest else dest_pool[0]
            chosen_identity = (
                random.choice(self.identities) if self.cfg.rand_source else identity
            )
            dest_mac = self._resolve_dest_mac(dest_ip)
            try:
                frames = build_frames(self.cfg, chosen_identity, dest_ip, dest_mac)
            except Exception:
                self.stats.bump_error()
                if self.cfg.verbose:
                    print("Failed to craft packet for", dest_ip)
                return

            if self.cfg.dry_run:
                for frame in frames:
                    print(frame.summary())
                return

            for frame in frames:
                try:
                    if self.writer:
                        self.writer.write(frame)
                    sendp(frame, iface=self.cfg.interface, verbose=0)
                    self.stats.bump_sent()
                except Exception:
                    self.stats.bump_error()
                    if self.cfg.verbose:
                        print("Send error for", dest_ip)

            sends += 1
            if count_limit and sends >= count_limit:
                break
            if not self.cfg.flood:
                time.sleep(max(self.cfg.interval, 0.0))

    def _resolve_dest_mac(self, dest_ip: str) -> str:
        if dest_ip in self.dest_mac_cache:
            return self.dest_mac_cache[dest_ip]
        mac = getmacbyip(dest_ip) or "ff:ff:ff:ff:ff:ff"
        self.dest_mac_cache[dest_ip] = mac
        return mac

    def _report_loop(self) -> None:
        while not self.stop_event.is_set():
            time.sleep(1)
            print(f"sent={self.stats.sent} errors={self.stats.errors}")


def _build_dest_pool(cfg: RuntimeConfig) -> List[str]:
    if cfg.rand_dest and cfg.dest_subnet:
        subnet = ipaddress.ip_network(cfg.dest_subnet, strict=False)
        return [str(ip) for ip in subnet.hosts()]
    if cfg.dst:
        return [cfg.dst]
    return []
