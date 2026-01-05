# ManyConnect: AnyConnect Namespace Automation

`namespace_anyconnect.py` provisions Linux network namespaces backed by veth
pairs, wires up NAT, and launches isolated Cisco AnyConnect tunnels using
`openconnect`. Each namespace acts like a distinct AnyConnect client, letting
one host simulate many parallel VPN users while keeping routes and DNS
separated.

## Quick start

Run as root (or via sudo):

```bash
sudo python manyconnect/namespace_anyconnect.py create \
  --sessions 3 \
  --server 203.0.113.10 \
  --username qa_user \
  --password 'S3cret!'
```

Tear everything down when finished:

```bash
sudo python manyconnect/namespace_anyconnect.py destroy --sessions 3
```

For non-interactive secrets, prefer `--password-env`, `--password-file`, or
`--password-command` over `--password`.

## Configuration file (optional)

When you need per-namespace overrides, supply a JSON or YAML file:

```json
{
  "external_interface": "eth0",
  "base_subnet": "10.200.0.0/16",
  "namespaces": [
    {
      "name": "qa-east",
      "vpn": {
        "server": "vpn.example.com",
        "user": "qa_east",
        "password_env": "QA_EAST_PASSWORD"
      }
    },
    {
      "name": "qa-west",
      "subnet": "10.200.1.0/30",
      "vpn": {
        "server": "vpn2.example.com",
        "user": "qa_west",
        "password_file": "/secure/qa_west.pass",
        "extra_args": ["--no-dtls"]
      }
    }
  ]
}
```

Create namespaces (with monitoring) from the config:

```bash
sudo python manyconnect/namespace_anyconnect.py --config vpn-namespaces.json create --monitor
```

Use `Ctrl+C` to stop monitored sessions, or run the destroy command later to
remove namespaces and NAT rules. Add `--skip-vpn` if you only want the namespace
and networking scaffolding without starting `openconnect`.
