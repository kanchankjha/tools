import logging
from typing import Dict, Iterable, List, Optional

log = logging.getLogger(__name__)


class NamespaceManager:
    """Handles netns, veth, and routing setup (currently plan-only)."""

    def __init__(self, interface: str):
        self.interface = interface

    def create_pod(
        self,
        name: str,
        ip: str,
        dns_servers: Optional[Iterable[str]] = None,
        include_routes: Optional[Iterable[str]] = None,
    ) -> Dict[str, List[str]]:
        """Return the planned commands for creating a namespace."""
        dns_servers = list(dns_servers or [])
        include_routes = list(include_routes or [])
        commands = [
            f"ip netns add {name}",
            f"ip link add {name}-host type veth peer name {name}-pod",
            f"ip link set {name}-pod netns {name}",
            f"ip addr add {ip} dev {name}-pod",
            f"ip -n {name} link set {name}-pod up",
            f"ip link set {name}-host up",
            f"ip route add default dev {name}-host",
        ]

        for route in include_routes:
            commands.append(f"ip -n {name} route add {route} dev {name}-pod")

        if dns_servers:
            resolv_lines = "\\n".join(f"nameserver {addr}" for addr in dns_servers)
            commands.append(f"echo '{resolv_lines}' > /etc/netns/{name}/resolv.conf")

        log.info("Planned namespace setup for %s via %s", name, self.interface)
        return {"name": name, "commands": commands}

    def destroy_pod(self, name: str) -> List[str]:
        """Return the planned commands for tearing down a namespace."""
        commands = [
            f"ip link del {name}-host || true",
            f"ip netns del {name} || true",
        ]
        log.info("Planned namespace teardown for %s", name)
        return commands
