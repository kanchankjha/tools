#!/usr/bin/env python3
"""Automate Linux network namespaces with Cisco AnyConnect (openconnect) sessions.

The script creates one veth-backed namespace per AnyConnect session, configures
NAT on the host, then launches `openconnect` inside each namespace so every VPN
tunnel stays isolated. Namespaces can be torn down via the `destroy`
sub-command.

Quick start (no config file required):

    sudo python namespace_anyconnect.py create \\
      --sessions 3 \\
      --server 203.0.113.10 \\
      --username qa_user \\
      --password 'S3cret!'

Advanced users can still supply a JSON/YAML config file that describes
per-namespace overrides (see README for details).
"""

from __future__ import annotations

import argparse
import ipaddress
import json
import os
import re
import signal
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional


# ------------------------------ CLI parsing --------------------------------- #


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Create network namespaces and start Cisco AnyConnect (openconnect) "
            "sessions inside each namespace."
        )
    )
    parser.add_argument(
        "--config",
        type=Path,
        help="Optional JSON/YAML config describing namespaces and VPN settings.",
    )
    parser.add_argument(
        "--base-subnet",
        dest="base_subnet",
        help="Override the default subnet pool (CIDR) used when config lacks per-namespace subnets.",
    )
    parser.add_argument(
        "--external-interface",
        dest="external_interface",
        help="Host interface used for NAT (defaults to config value or auto-detected default route).",
    )
    parser.add_argument(
        "--openconnect",
        dest="openconnect_path",
        help="Path to the openconnect binary (defaults to value in config or $PATH lookup).",
    )
    parser.add_argument(
        "--log-dir",
        dest="log_dir",
        type=Path,
        help="Directory for per-namespace openconnect logs (defaults to ./anyconnect-logs).",
    )
    parser.add_argument(
        "--enable-ip-forward",
        dest="enable_ip_forward",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Toggle automatic enabling of net.ipv4.ip_forward when absent (default: enable).",
    )
    parser.add_argument(
        "--sessions",
        type=int,
        help="Number of AnyConnect sessions to create when no config file is provided.",
    )
    parser.add_argument(
        "--server",
        help="AnyConnect server hostname or IP (used across auto-generated namespaces).",
    )
    parser.add_argument(
        "--username",
        help="VPN username for auto-generated namespaces.",
    )
    parser.add_argument(
        "--password",
        help="VPN password for auto-generated namespaces (use with caution; prefer --password-env).",
    )
    parser.add_argument(
        "--password-env",
        dest="password_env",
        help="Environment variable name that stores the VPN password.",
    )
    parser.add_argument(
        "--password-file",
        dest="password_file",
        help="File containing the VPN password.",
    )
    parser.add_argument(
        "--password-command",
        dest="password_command",
        help="Shell command that prints the VPN password to stdout.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    create = subparsers.add_parser("create", help="Create namespaces and launch openconnect.")
    create.add_argument(
        "--monitor",
        action="store_true",
        help="Stay in the foreground and restart openconnect if it exits; Ctrl+C tears everything down.",
    )
    create.add_argument(
        "--force",
        action="store_true",
        help="Recreate namespaces if they already exist (kills openconnect if necessary).",
    )
    create.add_argument(
        "--skip-vpn",
        action="store_true",
        help="Create namespaces and networking but do not launch openconnect.",
    )

    destroy = subparsers.add_parser("destroy", help="Stop openconnect sessions and remove namespaces.")
    destroy.add_argument(
        "--leave-namespaces",
        action="store_true",
        help="Stop VPN processes but keep namespaces and veth pairs in place.",
    )

    return parser


# ------------------------------ Data models --------------------------------- #


@dataclass
class NamespaceSpec:
    name: str
    host_iface: str
    ns_iface: str
    network: ipaddress.IPv4Network
    host_ip: str
    ns_ip: str
    vpn: Dict[str, object] = field(default_factory=dict)
    process: Optional[subprocess.Popen] = None
    log_path: Optional[Path] = None


# ------------------------------ Helpers ------------------------------------- #


def die(message: str, exit_code: int = 1) -> None:
    print(f"error: {message}", file=sys.stderr)
    sys.exit(exit_code)


def load_config(path: Path) -> Dict[str, object]:
    if not path.exists():
        die(f"config file {path} does not exist")

    text = path.read_text()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        try:
            import yaml  # type: ignore
        except ImportError as exc:
            die(
                "config is not valid JSON and PyYAML is unavailable; "
                "install pyyaml or provide JSON (pip install pyyaml)",
            )
        return yaml.safe_load(text)  # type: ignore[no-any-return]


def build_cli_config(args: argparse.Namespace) -> Dict[str, object]:
    if args.sessions is None:
        die("when --config is not supplied, --sessions must be provided")
    if args.sessions < 1:
        die("--sessions must be at least 1")

    launching_vpn = args.command == "create" and not getattr(args, "skip_vpn", False)
    if launching_vpn and not args.server:
        die("when launching VPN sessions without a config file, --server is required")
    if launching_vpn and not args.username:
        die("when launching VPN sessions without a config file, --username is required")

    vpn_secret: Dict[str, str] = {}
    if launching_vpn:
        if args.password:
            vpn_secret["password"] = args.password
        elif args.password_env:
            vpn_secret["password_env"] = args.password_env
        elif args.password_file:
            vpn_secret["password_file"] = args.password_file
        elif args.password_command:
            vpn_secret["password_command"] = args.password_command
        else:
            die(
                "provide --password, --password-env, --password-file, or --password-command "
                "when auto-generating namespaces"
            )
    else:
        if args.password:
            vpn_secret["password"] = args.password
        elif args.password_env:
            vpn_secret["password_env"] = args.password_env
        elif args.password_file:
            vpn_secret["password_file"] = args.password_file
        elif args.password_command:
            vpn_secret["password_command"] = args.password_command

    server = args.server or ""
    username = args.username or ""

    namespaces: List[Dict[str, object]] = []
    for idx in range(args.sessions):
        name = f"acns{idx + 1}"
        namespaces.append(
            {
                "name": name,
                "vpn": {
                    "server": server,
                    "user": username,
                    **vpn_secret,
                },
            }
        )

    config: Dict[str, object] = {
        "base_subnet": args.base_subnet or "10.200.0.0/16",
        "external_interface": args.external_interface,
        "openconnect_path": args.openconnect_path,
        "log_dir": str(args.log_dir) if args.log_dir else "./anyconnect-logs",
        "namespaces": namespaces,
    }
    return config


def which_openconnect(explicit: Optional[str]) -> str:
    if explicit:
        return explicit
    from shutil import which

    path = which("openconnect")
    if not path:
        die("openconnect not found in PATH; install it or set --openconnect")
    return path


def default_interface() -> Optional[str]:
    try:
        result = subprocess.run(
            ["ip", "route", "show", "default"],
            check=True,
            text=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError:
        return None
    for line in result.stdout.splitlines():
        parts = line.split()
        if "dev" in parts:
            idx = parts.index("dev")
            if idx + 1 < len(parts):
                return parts[idx + 1]
    return None


def netns_exists(name: str) -> bool:
    result = subprocess.run(
        ["ip", "netns", "list"],
        check=True,
        text=True,
        capture_output=True,
    )
    return any(line.split()[0] == name for line in result.stdout.splitlines())


def iface_exists(name: str) -> bool:
    result = subprocess.run(
        ["ip", "-o", "link", "show", "dev", name],
        text=True,
        capture_output=True,
    )
    return result.returncode == 0


def run(cmd: Iterable[str], *, check: bool = True, capture_output: bool = False) -> subprocess.CompletedProcess:
    kwargs = {"text": True}
    if capture_output:
        kwargs["capture_output"] = True
    print(f"+ {' '.join(cmd)}")
    return subprocess.run(list(cmd), check=check, **kwargs)


def ensure_ip_forward(enabled: bool) -> None:
    path = Path("/proc/sys/net/ipv4/ip_forward")
    if not path.exists() or not enabled:
        return
    try:
        current = path.read_text().strip()
        if current == "1":
            return
        path.write_text("1\n")
        print("+ net.ipv4.ip_forward enabled")
    except PermissionError:
        die("failed to enable net.ipv4.ip_forward; run as root or toggle --no-enable-ip-forward")


def sanitize_iface_name(namespace: str, suffix: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]", "", namespace)
    if not cleaned:
        cleaned = "ns"
    base = f"{cleaned[:10]}{suffix}"
    return base[:15]


def subnet_host_pair(network: ipaddress.IPv4Network) -> tuple[str, str]:
    hosts = list(network.hosts())
    if len(hosts) < 2:
        die(f"subnet {network} does not provide at least two usable addresses")
    return str(hosts[0]), str(hosts[1])


def iptables_has_rule(subnet: ipaddress.IPv4Network, iface: str) -> bool:
    cmd = [
        "iptables",
        "-t",
        "nat",
        "-C",
        "POSTROUTING",
        "-s",
        str(subnet),
        "-o",
        iface,
        "-j",
        "MASQUERADE",
    ]
    result = subprocess.run(cmd, capture_output=True)
    return result.returncode == 0


def add_masquerade(subnet: ipaddress.IPv4Network, iface: str) -> None:
    if iptables_has_rule(subnet, iface):
        return
    run(
        [
            "iptables",
            "-t",
            "nat",
            "-A",
            "POSTROUTING",
            "-s",
            str(subnet),
            "-o",
            iface,
            "-j",
            "MASQUERADE",
        ]
    )


def remove_masquerade(subnet: ipaddress.IPv4Network, iface: str) -> None:
    cmd = [
        "iptables",
        "-t",
        "nat",
        "-D",
        "POSTROUTING",
        "-s",
        str(subnet),
        "-o",
        iface,
        "-j",
        "MASQUERADE",
    ]
    subprocess.run(cmd)


def get_secret(vpn: Dict[str, object]) -> Optional[str]:
    if "password_env" in vpn:
        env = vpn["password_env"]
        if not isinstance(env, str):
            die("vpn.password_env must be a string")
        if env not in os.environ:
            die(f"environment variable {env} is not set for VPN password")
        return os.environ[env]
    if "password_file" in vpn:
        path = Path(str(vpn["password_file"]))
        if not path.exists():
            die(f"password file {path} does not exist")
        return path.read_text().strip()
    if "password" in vpn:
        return str(vpn["password"])
    if "password_command" in vpn:
        cmd = vpn["password_command"]
        if isinstance(cmd, list):
            result = subprocess.run(cmd, check=True, text=True, capture_output=True)
        elif isinstance(cmd, str):
            result = subprocess.run(cmd, shell=True, check=True, text=True, capture_output=True)
        else:
            die("vpn.password_command must be a string or list")
        return result.stdout.strip()
    return None


def ensure_log_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def terminate_process(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    try:
        proc.send_signal(signal.SIGINT)
        try:
            proc.wait(timeout=10)
            return
        except subprocess.TimeoutExpired:
            proc.terminate()
            proc.wait(timeout=5)
    except Exception:
        proc.kill()


# ------------------------------ Manager ------------------------------------- #


class NamespaceManager:
    def __init__(self, args: argparse.Namespace, config: Dict[str, object]):
        self.args = args
        self.config = config
        self.openconnect_path = which_openconnect(
            args.openconnect_path or config.get("openconnect_path")
        )
        base_cidr = args.base_subnet or config.get("base_subnet") or "10.200.0.0/16"
        self.base_network = ipaddress.ip_network(base_cidr, strict=False)
        self.external_iface = (
            args.external_interface
            or config.get("external_interface")
            or default_interface()
        )
        if not self.external_iface:
            die(
                "unable to detect external interface; specify via config external_interface or --external-interface"
            )
        self.log_dir = ensure_log_dir(
            args.log_dir or Path(config.get("log_dir", "./anyconnect-logs"))
        )
        namespaces = config.get("namespaces")
        if not isinstance(namespaces, list) or not namespaces:
            die("config.namespaces must be a non-empty list")
        self.namespace_specs: List[NamespaceSpec] = self._build_specs(namespaces)

    # --------------------- spec construction --------------------- #
    def _build_specs(self, configs: List[Dict[str, object]]) -> List[NamespaceSpec]:
        specs: List[NamespaceSpec] = []
        subnet_iter = self.base_network.subnets(new_prefix=30)
        for entry in configs:
            if "name" not in entry:
                die("each namespace entry must have a 'name'")
            name = str(entry["name"])
            supplied_subnet = entry.get("subnet")
            if supplied_subnet:
                network = ipaddress.ip_network(str(supplied_subnet), strict=False)
            else:
                try:
                    network = next(subnet_iter)
                except StopIteration:
                    die(
                        "not enough space in base_subnet to allocate /30 per namespace; "
                        "expand the pool or set explicit subnets"
                    )
            host_ip, ns_ip = subnet_host_pair(network)
            host_iface = sanitize_iface_name(name, "h")
            ns_iface = sanitize_iface_name(name, "n")
            vpn_cfg = entry.get("vpn", {})
            if not isinstance(vpn_cfg, dict):
                die(f"vpn config for namespace {name} must be a dict")
            specs.append(
                NamespaceSpec(
                    name=name,
                    host_iface=host_iface,
                    ns_iface=ns_iface,
                    network=network,
                    host_ip=host_ip,
                    ns_ip=ns_ip,
                    vpn=vpn_cfg,
                )
            )
        return specs

    # --------------------- create workflow ----------------------- #
    def create_all(self) -> None:
        if os.geteuid() != 0:
            die("run the script as root (network namespace manipulation requires root)")
        ensure_ip_forward(self.args.enable_ip_forward)
        for spec in self.namespace_specs:
            if self.args.force and netns_exists(spec.name):
                print(f"# removing existing namespace {spec.name} due to --force")
                self._destroy_namespace(spec, leave_ns=False)
            self._ensure_namespace(spec)
            add_masquerade(spec.network, self.external_iface)
            if not self.args.skip_vpn:
                spec.log_path = self.log_dir / f"{spec.name}.log"
                spec.process = self._start_openconnect(spec)

    # --------------------- destroy workflow ---------------------- #
    def destroy_all(self) -> None:
        missing = [spec.name for spec in self.namespace_specs if not netns_exists(spec.name)]
        if missing:
            print(f"# namespaces not present (nothing to destroy): {', '.join(missing)}")
        for spec in self.namespace_specs:
            if netns_exists(spec.name):
                self._destroy_namespace(spec, leave_ns=self.args.leave_namespaces if hasattr(self.args, "leave_namespaces") else False)
            remove_masquerade(spec.network, self.external_iface)

    # --------------------- monitoring ---------------------------- #
    def monitor(self) -> None:
        try:
            while True:
                for spec in self.namespace_specs:
                    proc = spec.process
                    if not proc:
                        continue
                    ret = proc.poll()
                    if ret is not None:
                        print(f"# openconnect exited for {spec.name} with code {ret}; restarting in 5s")
                        time.sleep(5)
                        spec.process = self._start_openconnect(spec)
                time.sleep(3)
        except KeyboardInterrupt:
            print("\n# interrupt received; tearing down namespaces")
            for spec in self.namespace_specs:
                if spec.process:
                    terminate_process(spec.process)
            for spec in self.namespace_specs:
                self._destroy_namespace(spec, leave_ns=False)
                remove_masquerade(spec.network, self.external_iface)

    # --------------------- namespace setup helpers --------------- #
    def _ensure_namespace(self, spec: NamespaceSpec) -> None:
        if not netns_exists(spec.name):
            run(["ip", "netns", "add", spec.name])
        if iface_exists(spec.host_iface):
            run(["ip", "link", "delete", spec.host_iface], check=False)
        run(
            [
                "ip",
                "link",
                "add",
                spec.host_iface,
                "type",
                "veth",
                "peer",
                "name",
                spec.ns_iface,
            ]
        )
        run(["ip", "link", "set", spec.ns_iface, "netns", spec.name])
        run(["ip", "link", "set", spec.host_iface, "up"])
        run(["ip", "addr", "replace", f"{spec.host_ip}/{spec.network.prefixlen}", "dev", spec.host_iface])
        run(["ip", "netns", "exec", spec.name, "ip", "link", "set", "lo", "up"])
        run(["ip", "netns", "exec", spec.name, "ip", "link", "set", spec.ns_iface, "up"])
        run(
            [
                "ip",
                "netns",
                "exec",
                spec.name,
                "ip",
                "addr",
                "replace",
                f"{spec.ns_ip}/{spec.network.prefixlen}",
                "dev",
                spec.ns_iface,
            ]
        )
        run(
            [
                "ip",
                "netns",
                "exec",
                spec.name,
                "ip",
                "route",
                "replace",
                "default",
                "via",
                spec.host_ip,
            ]
        )

    def _destroy_namespace(self, spec: NamespaceSpec, *, leave_ns: bool) -> None:
        if spec.process:
            terminate_process(spec.process)
        if netns_exists(spec.name):
            run(["ip", "netns", "exec", spec.name, "pkill", "-TERM", "openconnect"], check=False)
        if not leave_ns:
            if iface_exists(spec.host_iface):
                run(["ip", "link", "delete", spec.host_iface], check=False)
            if netns_exists(spec.name):
                run(["ip", "netns", "delete", spec.name])

    # --------------------- openconnect launch -------------------- #
    def _start_openconnect(self, spec: NamespaceSpec) -> subprocess.Popen:
        vpn = spec.vpn
        required = ("server", "user")
        for key in required:
            if key not in vpn:
                die(f"vpn config for namespace {spec.name} is missing '{key}'")

        cmd: List[str] = [
            "ip",
            "netns",
            "exec",
            spec.name,
            self.openconnect_path,
            "--protocol",
            "anyconnect",
            "--user",
            str(vpn["user"]),
            "--passwd-on-stdin",
        ]
        if "authgroup" in vpn:
            cmd.extend(["--authgroup", str(vpn["authgroup"])])
        if "csd-wrapper" in vpn:
            cmd.extend(["--csd-wrapper", str(vpn["csd-wrapper"])])
        if "proxy" in vpn:
            cmd.extend(["--proxy", str(vpn["proxy"])])
        extra_args = vpn.get("extra_args")
        if isinstance(extra_args, list):
            cmd.extend(str(arg) for arg in extra_args)
        elif extra_args is not None:
            die(f"vpn.extra_args for namespace {spec.name} must be a list")
        cmd.append(str(vpn["server"]))

        log_file = spec.log_path.open("a") if spec.log_path else subprocess.DEVNULL
        password = get_secret(vpn)
        stdin = subprocess.PIPE if password is not None else None
        print(f"# starting openconnect for namespace {spec.name}")
        proc = subprocess.Popen(
            cmd,
            stdin=stdin,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            text=True,
        )
        if password is not None and proc.stdin:
            proc.stdin.write(password + "\n")
            proc.stdin.flush()
            proc.stdin.close()
        if stdin is None:
            print(
                f"# openconnect for {spec.name} is interactive; attach via "
                f'`ip netns exec {spec.name} {self.openconnect_path} ...` if needed'
            )
        return proc


# ------------------------------ Entrypoint ---------------------------------- #


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.config:
        config = load_config(args.config)
    else:
        config = build_cli_config(args)
    manager = NamespaceManager(args, config)
    if args.command == "create":
        manager.create_all()
        if args.monitor:
            manager.monitor()
        else:
            print("# namespaces created; run `destroy` when finished to tear down")
    elif args.command == "destroy":
        manager.destroy_all()


if __name__ == "__main__":
    main()
