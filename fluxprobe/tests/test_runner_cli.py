from typing import Optional
import sys

import pytest

from fluxprobe import cli
from fluxprobe import runner as runner_mod
from fluxprobe.runner import FuzzRunner, FuzzConfig
from fluxprobe.schema import protocol_from_dict


class FakeTransport:
    def __init__(self):
        self.sent = []
        self.recv_called = 0
        self.closed = False

    def send(self, data: bytes) -> None:
        self.sent.append(data)

    def recv(self, bufsize: int = 4096, timeout: Optional[float] = None) -> bytes:
        self.recv_called += 1
        return b"resp"

    def close(self) -> None:
        self.closed = True


def test_runner_uses_transport_and_logs(tmp_path, monkeypatch):
    schema = protocol_from_dict(
        {
            "name": "Echo",
            "transport": {"type": "tcp", "host": "127.0.0.1", "port": 1},
            "message": {
                "fields": [
                    {"name": "opcode", "type": "u8", "default": 1},
                    {"name": "len", "type": "u16", "length_of": "payload"},
                    {"name": "payload", "type": "bytes", "min_length": 1, "max_length": 2},
                ]
            },
        }
    )
    fake_transport = FakeTransport()
    monkeypatch.setattr(runner_mod, "create_transport", lambda spec: fake_transport)
    log_file = tmp_path / "run.log"
    monkeypatch.setattr("time.sleep", lambda x: None)
    runner = FuzzRunner(
        schema,
        FuzzConfig(iterations=3, mutation_rate=0.5, recv_timeout=0.1, seed=42, log_file=log_file, delay_ms=1),
    )
    runner.run()
    assert fake_transport.sent  # data was sent
    assert fake_transport.closed
    assert log_file.exists()


def test_runner_dry_run_skips_transport_and_logs(tmp_path, monkeypatch):
    schema = protocol_from_dict(
        {
            "name": "Echo",
            "transport": {"type": "tcp", "host": "127.0.0.1", "port": 1},
            "message": {
                "fields": [
                    {"name": "opcode", "type": "u8", "default": 1},
                ]
            },
        }
    )

    def fail_transport(_):
        raise AssertionError("transport should not be created in dry-run mode")

    monkeypatch.setattr(runner_mod, "create_transport", fail_transport)
    log_file = tmp_path / "dry.log"
    runner = FuzzRunner(schema, FuzzConfig(iterations=2, mutation_rate=0.0, dry_run=True, log_file=log_file, seed=1))
    runner.run()
    contents = log_file.read_text()
    assert "dry_run=True" in contents
    assert "DRY-RUN" in contents


def test_cli_protocol_and_target(monkeypatch):
    # Use a minimal schema via profile loader stub.
    minimal_schema = protocol_from_dict(
        {
            "name": "Mini",
            "transport": {"type": "tcp", "host": "1.1.1.1", "port": 80},
            "message": {
                "fields": [
                    {"name": "b", "type": "u8", "default": 1},
                ]
            },
        }
    )
    runner_called = {}

    monkeypatch.setattr(cli, "load_profile", lambda name: minimal_schema)
    monkeypatch.setattr(
        cli.FuzzRunner,
        "run",
        lambda self: runner_called.update({"host": self.schema.transport.host, "port": self.schema.transport.port}),
    )

    argv = ["prog", "--protocol", "echo", "--target", "10.0.0.5:9999", "--iterations", "1"]
    monkeypatch.setattr(sys, "argv", argv)
    cli.main()
    assert runner_called == {"host": "10.0.0.5", "port": 9999}


def test_cli_requires_protocol_or_schema(monkeypatch):
    argv = ["prog"]
    monkeypatch.setattr(sys, "argv", argv)
    with pytest.raises(SystemExit):
        cli.main()


def test_main_module_importable():
    # Importing __main__ should not execute runner but should expose main callable.
    import fluxprobe.__main__ as entry

    assert callable(entry.main)


def test_cli_schema_path(monkeypatch, tmp_path):
    schema_path = tmp_path / "schema.json"
    schema_path.write_text(
        '{"name": "json", "transport": {"type": "tcp", "host": "1.1.1.1", "port": 5},'
        '"message": {"fields": [{"name": "x", "type": "u8", "default": 1}]}}'
    )
    captured = {}

    def fake_run(self):
        captured["host"] = self.schema.transport.host
        captured["port"] = self.schema.transport.port

    monkeypatch.setattr(cli.FuzzRunner, "run", fake_run)
    argv = ["prog", "--schema", str(schema_path), "--host", "2.2.2.2", "--port", "99", "--iterations", "1"]
    monkeypatch.setattr(sys, "argv", argv)
    cli.main()
    assert captured == {"host": "2.2.2.2", "port": 99}


def test_main_runs_via_runpy(monkeypatch):
    import runpy

    captured = {}
    minimal_schema = protocol_from_dict(
        {
            "name": "Mini",
            "transport": {"type": "tcp", "host": "1.1.1.1", "port": 80},
            "message": {"fields": [{"name": "b", "type": "u8", "default": 1}]},
        }
    )
    monkeypatch.setattr(cli, "load_profile", lambda name: minimal_schema)
    monkeypatch.setattr(cli.FuzzRunner, "run", lambda self: captured.update({"ran": True}))
    monkeypatch.setattr(sys, "argv", ["prog", "--protocol", "echo", "--target", "1.1.1.1:1", "--iterations", "1"])
    runpy.run_module("fluxprobe.__main__", run_name="__main__")
    assert captured == {"ran": True}


def test_cli_target_format_validation(monkeypatch):
    argv = ["prog", "--protocol", "echo", "--target", "badtarget"]
    monkeypatch.setattr(sys, "argv", argv)
    with pytest.raises(SystemExit):
        cli.main()


def test_cli_target_ipv6(monkeypatch):
    captured = {}
    minimal_schema = protocol_from_dict(
        {
            "name": "Mini",
            "transport": {"type": "tcp", "host": "1.1.1.1", "port": 80},
            "message": {"fields": [{"name": "b", "type": "u8", "default": 1}]},
        }
    )
    monkeypatch.setattr(cli, "load_profile", lambda name: minimal_schema)
    monkeypatch.setattr(cli.FuzzRunner, "run", lambda self: captured.update({"host": self.schema.transport.host, "port": self.schema.transport.port}))
    argv = ["prog", "--protocol", "echo", "--target", "[::1]:443", "--iterations", "1"]
    monkeypatch.setattr(sys, "argv", argv)
    cli.main()
    assert captured == {"host": "::1", "port": 443}


def test_cli_sets_dry_run(monkeypatch):
    captured = {}
    minimal_schema = protocol_from_dict(
        {
            "name": "Mini",
            "transport": {"type": "tcp", "host": "1.1.1.1", "port": 80},
            "message": {"fields": [{"name": "b", "type": "u8", "default": 1}]},
        }
    )
    monkeypatch.setattr(cli, "load_profile", lambda name: minimal_schema)
    monkeypatch.setattr(
        cli.FuzzRunner,
        "run",
        lambda self: captured.update({"dry_run": self.config.dry_run, "host": self.schema.transport.host}),
    )
    argv = ["prog", "--protocol", "echo", "--target", "1.1.1.1:80", "--iterations", "1", "--dry-run"]
    monkeypatch.setattr(sys, "argv", argv)
    cli.main()
    assert captured == {"dry_run": True, "host": "1.1.1.1"}
