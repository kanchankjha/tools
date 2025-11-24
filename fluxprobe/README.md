# FluxProbe

FluxProbe is a lightweight, schema-driven protocol fuzzer. Point it at a protocol description, and it will emit a mix of valid and intentionally corrupted frames, send them to your device-under-test (DUT), and log what happens. The goal is to reproduce the fast iteration of commercial fuzzers (e.g., Codenomicon) with an open, hackable core.

## Features
- Declarative protocol schemas (YAML/JSON) with primitive field types, enums, and length references.
- Valid frame generator plus structure-aware and byte-level mutators (off-by-one lengths, invalid enums, bit flips, trunc/extend, checksum tamper hooks).
- Pluggable transports (TCP/UDP) and a simple run loop with rate limiting and timeouts.
- Deterministic runs via `--seed`, with hexdump logging for replay.

## Quickstart
- Built-in profiles (no YAML needed): `python -m fluxprobe --protocol http --target 10.0.0.5:8080 --iterations 200 --mutation-rate 0.4`
- Using a schema file: `python -m fluxprobe --schema examples/protocols/echo.yaml --host 127.0.0.1 --port 9000 --iterations 200 --mutation-rate 0.4`

Available built-in `--protocol` profiles: `echo`, `http`, `dns`, `mqtt`, `modbus`, `coap`, `tcp`, `udp`, `ip`, `snmp`, `ssh`.

## Schema Format (MVP)

```yaml
name: Demo Echo
transport:
  type: tcp       # tcp | udp
  host: 127.0.0.1
  port: 9000
message:
  fields:
    - name: opcode
      type: enum
      choices: [0x01, 0x02, 0xFF]
      default: 0x01
    - name: payload_length
      type: u16
      length_of: payload   # will be set automatically to len(payload)
    - name: payload
      type: bytes
      min_length: 0
      max_length: 32
      fuzz_values: ["", "A", "BEEF"]
```

Supported field types:
- `u8`, `u16`, `u32` (big endian), `bytes`, `string` (ASCII/UTF-8).
- `enum` (numeric choices or strings).
- `length_of` lets one field mirror the length of another field.
- `min_value` / `max_value` for numeric bounds, `min_length` / `max_length` for blobs.

## CLI
- `--protocol`: use a built-in profile (see list above)
- `--schema`: path to YAML/JSON schema (if not using `--protocol`)
- `--target`: shorthand host:port override (e.g., `10.0.0.5:8080`)
- `--host` / `--port`: override transport endpoints
- `--iterations`: number of frames to send (default 100)
- `--mutation-rate`: fraction of frames to mutate (0.0 = only valid, 1.0 = always mutated)
- `--mutations-per-frame`: how many mutation operations to apply (default 1)
- `--recv-timeout`: seconds to wait for responses (0 to skip)
- `--seed`: RNG seed for reproducibility
- `--log-file`: optional log path (hexdumps + metadata)

## Structure
- `fluxprobe/` — core library (schema loader, generator, mutators, transports, runner, CLI)
- `examples/protocols/` — sample schemas to adapt (echo, HTTP, DNS, MQTT, Modbus/TCP, CoAP, TCP raw, UDP payload, IPv4 packet, SNMP, SSH)

## Roadmap Ideas
- Coverage-guided mode, PCAP import for seeds, checksum helpers, richer state machines, web dashboard.
