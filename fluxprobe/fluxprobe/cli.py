import argparse
import logging
from pathlib import Path

from .runner import FuzzConfig, FuzzRunner
from .schema import load_protocol_schema
from .profiles import BUILTIN_SCHEMAS, load_profile


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="FluxProbe - schema-driven protocol fuzzer")
    parser.add_argument("--protocol", choices=sorted(BUILTIN_SCHEMAS.keys()), help="Use a built-in protocol profile")
    parser.add_argument("--schema", help="Path to protocol schema (YAML/JSON) if not using --protocol")
    parser.add_argument("--target", help="Convenience host:port for overrides")
    parser.add_argument("--host", help="Override transport host")
    parser.add_argument("--port", type=int, help="Override transport port")
    parser.add_argument("--iterations", type=int, default=100, help="Number of frames to send")
    parser.add_argument("--mutation-rate", type=float, default=0.3, help="Probability to mutate a frame")
    parser.add_argument("--mutations-per-frame", type=int, default=1, help="How many mutation ops per mutated frame")
    parser.add_argument("--payload-size", type=int, help="Force payload field size (bytes/string) and fill with default data")
    parser.add_argument("--recv-timeout", type=float, default=0.0, help="Seconds to wait for responses (0 to skip)")
    parser.add_argument("--seed", type=int, help="RNG seed for reproducibility")
    parser.add_argument("--delay-ms", type=int, default=0, help="Delay between sends in milliseconds")
    parser.add_argument("--log-file", type=Path, help="Optional log file path")
    parser.add_argument("--log-level", default="INFO", help="Logging level (DEBUG, INFO, WARNING)")
    return parser.parse_args()


def _parse_target(target: str) -> tuple[str, int]:
    # Support IPv6 in bracket form: [::1]:22
    if target.startswith("["):
        if "]" not in target:
            raise SystemExit("--target IPv6 must be like [addr]:port")
        host_part, _, port_part = target.partition("]")
        host = host_part[1:]
        if not port_part.startswith(":"):
            raise SystemExit("--target IPv6 must be like [addr]:port")
        port = port_part.lstrip(":")
    else:
        if ":" not in target:
            raise SystemExit("--target must be host:port")
        host, port = target.rsplit(":", 1)
    try:
        return host, int(port)
    except ValueError as exc:
        raise SystemExit("--target port must be an integer") from exc


def main() -> None:
    args = parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    if not args.protocol and not args.schema:
        raise SystemExit("Specify either --protocol <name> or --schema <path>")

    if args.protocol:
        schema = load_profile(args.protocol)
    else:
        schema_path = Path(args.schema)
        schema = load_protocol_schema(schema_path)

    if args.target:
        host, port = _parse_target(args.target)
        schema.transport.host = host
        schema.transport.port = port
    if args.host:
        schema.transport.host = args.host
    if args.port:
        schema.transport.port = args.port

    config = FuzzConfig(
        iterations=args.iterations,
        mutation_rate=args.mutation_rate,
        mutations_per_frame=args.mutations_per_frame,
        payload_size=args.payload_size,
        recv_timeout=args.recv_timeout,
        seed=args.seed,
        delay_ms=args.delay_ms,
        log_file=args.log_file,
    )
    runner = FuzzRunner(schema, config)
    runner.run()


if __name__ == "__main__":
    main()
