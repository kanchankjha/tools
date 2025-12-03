import ipaddress
import logging
from dataclasses import dataclass
from typing import Dict, Optional

log = logging.getLogger(__name__)


@dataclass
class Lease:
    name: str
    ip: ipaddress._BaseAddress


class IpAllocator:
    """Very small IPAM to hand out host addresses inside a subnet."""

    def __init__(self, subnet: str):
        self.network = ipaddress.ip_network(subnet, strict=False)
        self._leases: Dict[str, Lease] = {}

    def allocate(self, name: str) -> ipaddress._BaseAddress:
        """Return the next available host IP for a given name."""
        if name in self._leases:
            log.debug("IP already allocated for %s: %s", name, self._leases[name].ip)
            return self._leases[name].ip

        used = {lease.ip for lease in self._leases.values()}
        for host_ip in self.network.hosts():
            if host_ip in used:
                continue
            lease = Lease(name=name, ip=host_ip)
            self._leases[name] = lease
            log.info("Allocated %s to %s", host_ip, name)
            return host_ip

        raise RuntimeError("No free IPs available in subnet")

    def release(self, name: str) -> Optional[ipaddress._BaseAddress]:
        """Release the IP tied to a name."""
        lease = self._leases.pop(name, None)
        if lease:
            log.info("Released %s from %s", lease.ip, name)
            return lease.ip
        log.debug("Nothing to release for %s", name)
        return None

    def leases(self) -> Dict[str, Lease]:
        return dict(self._leases)
