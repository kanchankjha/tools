# hpsim (hping3-inspired simulator)

Python package that simulates many clients on one Linux host, sending hping3-style traffic with spoofed IP/MAC addresses from the same subnet.

## Install

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install --upgrade pip
pip install -r tools/hpsim/requirements.txt
pip install -e tools/hpsim
```

> Needs root or `sudo setcap cap_net_raw,cap_net_admin+ep .venv/bin/python` to send raw frames.

## Usage

```bash
hpsim --interface eth0 --clients 10 --dst 10.0.0.5 --dport 80 --proto tcp --flags S --count 100 --interval 0.01
```

Key flags:
- `--subnet-pool` CIDR to allocate client IPs (defaults to interface subnet)
- `--rand-source` randomize client identity per packet
- `--rand-dest --dest-subnet 10.0.0.0/24` randomize destination IPs
- `--payload "deadbeef" --payload-hex` send custom payload
- `--flood` remove delay, `--dry-run` craft packets only, `--pcap-out out.pcap` write sent frames

### CLI parameters

- `--config PATH` load YAML/JSON defaults
- `--interface IFACE` interface to send on (required)
- `--dst IP` destination IP (required unless using `--dest-subnet`)
- `--dest-subnet CIDR` pool for random destination IPs
- `--clients N` number of simulated clients (default 1)
- `--subnet-pool CIDR` pool for client source IPs (defaults to interface subnet)
- `--proto {tcp,udp,icmp}` protocol (default tcp)
- `--dport N` destination port (tcp/udp)
- `--sport N` source port (tcp/udp)
- `--flags STRING` TCP flags (default S)
- `--icmp-type N --icmp-code N` ICMP settings (default 8/0)
- `--ttl N` IP TTL (default 64), `--tos N` IP TOS (default 0), `--ip-id N` IP identification
- `--frag` enable fragmentation, `--frag-size N` fragment size bytes
- `--rand-source` randomize source identity per packet
- `--rand-dest` randomize destination per packet (uses `--dest-subnet` if provided)
- `--payload STRING` payload as text, `--payload-hex` interpret payload as hex
- `--count N` packets per client (0 = infinite)
- `--interval SECONDS` delay between packets (default 0.1); `--flood` removes delay
- `--pcap-out PATH` write sent frames to pcap
- `--dry-run` build packets only; `--verbose` print send/craft errors

## Layout

- `hpsim/` package code
- `pyproject.toml` packaging metadata
