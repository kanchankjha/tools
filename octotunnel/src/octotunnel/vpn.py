import logging
from typing import Dict, Iterable, List

log = logging.getLogger(__name__)


class VpnRunner:
    """Builds commands to launch and stop AnyConnect/OpenConnect sessions."""

    def start(
        self,
        pod_name: str,
        server: str,
        username: str,
        password_source: str,
        protocol: str = "anyconnect",
        extra_args: Iterable[str] | None = None,
    ) -> Dict[str, str]:
        extra_args = list(extra_args or [])
        command = [
            "ip",
            "netns",
            "exec",
            pod_name,
            "openconnect",
            f"--protocol={protocol}",
            f"--user={username}",
            "--passwd-on-stdin",
            server,
            *extra_args,
        ]
        log.info("Planned VPN start for %s -> %s using protocol=%s", pod_name, server, protocol)
        return {
            "name": pod_name,
            "server": server,
            "command": " ".join(command),
            "password_source": password_source,
        }

    def stop(self, pod_name: str) -> List[str]:
        log.info("Planned VPN stop for %s", pod_name)
        return [f"pkill -f 'ip netns exec {pod_name} openconnect' || true"]
