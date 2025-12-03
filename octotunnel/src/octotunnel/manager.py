import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional

from .ipam import IpAllocator
from .netns import NamespaceManager
from .vpn import VpnRunner

log = logging.getLogger(__name__)


@dataclass
class VpnSettings:
    server: str
    username: str
    password: str
    protocol: str = "anyconnect"
    extra_args: List[str] = field(default_factory=list)


@dataclass
class RoutingSettings:
    mode: str = "full"
    include: List[str] = field(default_factory=list)


@dataclass
class DnsSettings:
    servers: List[str] = field(default_factory=list)


@dataclass
class LoggingSettings:
    level: str = "info"
    directory: Optional[str] = None


@dataclass
class AppConfig:
    interface: str
    subnet: str
    instances: int
    vpn: VpnSettings
    routing: RoutingSettings = field(default_factory=RoutingSettings)
    dns: DnsSettings = field(default_factory=DnsSettings)
    logging: LoggingSettings = field(default_factory=LoggingSettings)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AppConfig":
        vpn_data = data.get("vpn", {})
        routing_data = data.get("routing", {})
        dns_data = data.get("dns", {})
        logging_data = data.get("logging", {})

        return cls(
            interface=data["interface"],
            subnet=data["subnet"],
            instances=int(data.get("instances", 1)),
            vpn=VpnSettings(
                server=vpn_data["server"],
                username=vpn_data["username"],
                password=vpn_data.get("password", ""),
                protocol=vpn_data.get("protocol", "anyconnect"),
                extra_args=list(vpn_data.get("extra_args", [])),
            ),
            routing=RoutingSettings(
                mode=routing_data.get("mode", "full"),
                include=list(routing_data.get("include", [])),
            ),
            dns=DnsSettings(servers=list(dns_data.get("servers", []))),
            logging=LoggingSettings(
                level=logging_data.get("level", "info"),
                directory=logging_data.get("directory"),
            ),
        )


class Controller:
    """Coordinates IP allocation, netns setup, and VPN command planning."""

    def __init__(self, config: AppConfig):
        self.config = config
        self.ipam = IpAllocator(config.subnet)
        self.netns = NamespaceManager(config.interface)
        self.vpn = VpnRunner()

    def launch(self) -> List[Dict[str, Any]]:
        plan: List[Dict[str, Any]] = []
        log.info(
            "Planning launch: %s instances on %s subnet via %s",
            self.config.instances,
            self.config.subnet,
            self.config.interface,
        )
        for idx in range(self.config.instances):
            pod_name = f"octopod-{idx + 1}"
            ip = self.ipam.allocate(pod_name)
            netns_plan = self.netns.create_pod(
                name=pod_name,
                ip=str(ip),
                dns_servers=self.config.dns.servers,
                include_routes=self._routes_for_mode(),
            )
            vpn_plan = self.vpn.start(
                pod_name=pod_name,
                server=self.config.vpn.server,
                username=self.config.vpn.username,
                password_source=self._password_hint(),
                protocol=self.config.vpn.protocol,
                extra_args=self.config.vpn.extra_args,
            )
            plan.append({"pod": pod_name, "ip": str(ip), "netns": netns_plan, "vpn": vpn_plan})
        return plan

    def status(self) -> Dict[str, str]:
        leases = self.ipam.leases()
        log.info("Current planned leases: %s", {k: str(v.ip) for k, v in leases.items()})
        return {name: str(lease.ip) for name, lease in leases.items()}

    def destroy(self, pods: Optional[Iterable[str]] = None) -> List[Dict[str, Any]]:
        commands: List[Dict[str, Any]] = []
        targets = list(pods) if pods else list(self.ipam.leases().keys())
        for pod in targets:
            teardown = self.netns.destroy_pod(pod)
            released_ip = self.ipam.release(pod)
            commands.append({"pod": pod, "released_ip": str(released_ip) if released_ip else None, "commands": teardown})
        return commands

    def _routes_for_mode(self) -> List[str]:
        if self.config.routing.mode == "full":
            return []
        return self.config.routing.include

    def _password_hint(self) -> str:
        if self.config.vpn.password.startswith("${"):
            return f"env:{self.config.vpn.password}"
        return "inline"
