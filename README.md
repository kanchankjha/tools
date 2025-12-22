# Tools

A collection of network testing, automation, and infrastructure tools for QA, security research, and load testing.

## Tools Overview

### 🔌 Network & VPN Tools

#### [AnyConnect](anyconnect/)
Provisions Linux network namespaces backed by veth pairs with isolated Cisco AnyConnect/OpenConnect tunnels. Each namespace targets a different VPN concentrator while keeping routes and DNS separated. Perfect for testing concurrent VPN sessions.

**Use cases:** Multi-tunnel testing, VPN load testing, isolated network testing

#### [OctoTunnel](octotunnel/)
Pod-like network namespace orchestrator that creates multiple isolated namespaces with unique IPs and independent AnyConnect sessions. Simulates Kubernetes-style pods without running a full cluster.

**Status:** Scaffold stage (design docs and stubs)
**Use cases:** Pod-per-connection patterns, VPN server validation, concurrent session testing

### 🚀 Traffic Generation & Fuzzing

#### [FluxGen](fluxgen/)
Powerful multi-client traffic generator inspired by hping3. Simulates hundreds of clients from a single Linux host with spoofed IP/MAC addresses. Supports TCP, UDP, ICMP, IGMP, GRE, ESP, AH, and SCTP protocols.

**Features:** Multi-client simulation, protocol flexibility, custom payloads, PCAP export, flood mode
**Use cases:** Network load testing, stress testing, security research

#### [FluxProbe](fluxprobe/)
Lightweight, schema-driven protocol fuzzer that emits valid and intentionally corrupted network frames. Designed to reproduce fast iteration of commercial fuzzers with an open, hackable core.

**Features:** Schema-driven fuzzing, PyYAML-based protocol descriptions
**Use cases:** Protocol fuzzing, vulnerability discovery, security testing

### ☁️ Cloud & Infrastructure

#### [K8s-500-VM-Automation](k8s-500-vm-automation/)
Provisions ~500 Kubernetes nodes on AWS with AnyConnect VPN integration. Uses Terraform for infrastructure, Ansible for bootstrapping, and deploys kubeadm with a ping DaemonSet for validation.

**Components:** Terraform (VPC, instances, NLB), Ansible (VPN setup, kubeadm), K8s manifests
**Use cases:** Large-scale K8s testing, VPN-integrated clusters, load testing infrastructure

#### [Meraki](meraki/)
Lightweight Meraki Dashboard automation toolkit with Python client and CLI. Wraps the Meraki v1 REST API for network and device management (create, read, update, delete).

**Features:** Network CRUD operations, device claiming/removal, config file support
**Use cases:** Meraki automation, bulk network provisioning, dashboard operations

#### [Meraki-Snapshot](meraki-snapshot/)
CLI tool to backup and restore Meraki Dashboard organization configurations. Crawls networks, captures per-product settings, and safely restores them with dry-run planning.

**Features:** Org-wide backups, safe restore planning, rate-limit handling, JSON storage
**Use cases:** Configuration backup, disaster recovery, config migration

### 🛠️ Utilities

#### [Command-Repeater](command-repeater/)
Python script that executes commands repeatedly with incrementing parameters, polling for status between executions. Automates load testing and batch processing workflows.

**Features:** Incremental parameter execution, status polling, configurable intervals
**Use cases:** Load testing, batch processing, service scaling, performance testing

## Getting Started

Each tool has its own README with detailed installation and usage instructions. Most tools require:
- Python 3.8+ (some tools require 3.9-3.12)
- Linux for network tools (raw socket support)
- Root privileges for packet-level operations

## Repository Structure

```
tools/
├── anyconnect/           # VPN namespace automation
├── command-repeater/     # Incremental command executor
├── fluxgen/             # Multi-client traffic generator
├── fluxprobe/           # Protocol fuzzer
├── k8s-500-vm-automation/ # Large-scale K8s on AWS
├── meraki/              # Meraki Dashboard automation
├── meraki-snapshot/     # Meraki config backup/restore
└── octotunnel/          # Multi-namespace VPN orchestrator
```

## License

See [LICENSE](LICENSE) for details.
