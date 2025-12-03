# OctoTunnel Architecture

## Goals
- Spin up N isolated VPN sessions that mirror Kubernetes pod separation.
- Assign per-session IPs from a host interface subnet; avoid collisions.
- Keep routing, DNS, and logs isolated per session.
- Make teardown idempotent; clean namespaces, veth pairs, and iptables rules.

## Non-goals (initial cut)
- Full Kubernetes API parity.
- VPN clients beyond AnyConnect/OpenConnect.
- Windows/macOS host support (focus: Linux).

## Components
- **Controller**: Parses config/CLI, drives lifecycle (launch, status, destroy).
- **IPAM**: Allocates/reclaims IPs inside the provided subnet; tracks leases.
- **Namespace builder**: Creates netns, veth pairs, assigns IP, sets routes/DNS.
- **VPN runner**: Starts `openconnect` with provided credentials; monitors health.
- **Observer**: Collects per-session logs/metrics and exposes status.

## High-level flow
1) Parse config (server, creds, interface, subnet, instance count, DNS, routes).
2) For each instance:
   - Allocate next free IP from subnet; reserve in IPAM.
   - Create `ip netns add <pod>` and a veth pair; move peer into netns.
   - Assign pod IP; set default route through host veth; optional NAT/masquerade.
   - Drop a per-namespace `resolv.conf` if provided.
   - Launch `openconnect` inside the namespace (via `ip netns exec`).
3) Watchdog monitors tunnels; restarts on failure with backoff.
4) Destroy tears down VPN, routes, veth, netns, and releases IP.

## Configuration sketch (YAML)
```yaml
interface: eth0
subnet: 10.20.30.0/24
instances: 4
vpn:
  server: vpn.example.com
  username: alice
  password: ${VPN_PASSWORD}
  protocol: anyconnect
  extra_args: ["--authgroup", "corp"]
routing:
  mode: full  # or split
  include: ["10.50.0.0/16"]
dns:
  servers: ["10.0.0.10", "10.0.0.11"]
logging:
  level: info
  directory: /var/log/octotunnel
```

## Security & ops notes
- Credentials should be pulled from env vars or a secret store; avoid logging secrets.
- Requires root or CAP_NET_ADMIN to create namespaces/veth and run `openconnect`.
- Clean teardown is critical; ensure idempotent delete of veth, namespaces, and iptables.
- Consider `systemd-run --user --pty` or container mode for tighter isolation later.
