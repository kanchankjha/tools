# OctoTunnel

OctoTunnel is a Linux-first orchestrator that spins up multiple pod-like network namespaces, assigns each a unique IP from a provided interface subnet, and launches independent AnyConnect/OpenConnect sessions with username/password authentication. Use it to test concurrent VPN sessions, isolate traffic, and simulate Kubernetes-style pods without running a full cluster.

## Status
- Scaffolding and design docs only; controller and namespace plumbing are still stubs.
- Targets Linux with `ip` (iproute2), `openconnect`, and Python 3.10+ available on the host.

## Why
- Reproduce pod-per-connection patterns without Kubernetes.
- Validate VPN server behavior under many concurrent sessions.
- Keep routes, DNS, and logs isolated per session.

## Project layout
- `src/octotunnel/`: Python package for the controller, IPAM, namespace, and VPN session management.
- `docs/architecture.md`: Goals, constraints, and component breakdown.
- `examples/config.example.yaml`: Example config covering subnet, interface, and VPN server credentials.

## Quick start (scaffold stage)
1) Ensure Linux tools are present: `ip`, `openconnect`, `iproute2`, and `python3`.
2) Create a virtual environment and install locally:
   ```bash
   cd octotunnel
   python -m venv .venv && source .venv/bin/activate
   pip install -e .
   ```
3) Draft a config:
   ```bash
   cp examples/config.example.yaml config.yaml
   # edit server, username, password, interface, and subnet
   ```
4) Run (stubbed today, wiring to follow):
   ```bash
   octotunnel launch --config config.yaml
   ```

## Planned capabilities
- IP allocation from an interface subnet with conflict checks and release.
- Per-pod veth + netns setup, isolated routing/DNS, and optional NAT to host.
- Concurrent `openconnect` sessions with retry/backoff and health checks.
- CLI to launch, list, and destroy sessions; JSON/YAML config support.
- Logs and metrics per pod for debugging or load testing.
