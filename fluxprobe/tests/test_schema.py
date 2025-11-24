import json
from pathlib import Path

import pytest

from fluxprobe.schema import protocol_from_dict, load_protocol_schema


def test_protocol_from_dict_defaults():
    schema = protocol_from_dict(
        {
            "transport": {"type": "tcp", "host": "h", "port": 1},
            "message": {"fields": [{"name": "x", "type": "u8", "default": 1}]},
        },
        default_name="demo",
    )
    assert schema.name == "demo"
    assert schema.transport.host == "h"
    assert schema.message.fields[0].name == "x"


def test_load_protocol_schema_json(tmp_path: Path):
    data = {
        "name": "jsonschema",
        "transport": {"type": "udp", "host": "1.2.3.4", "port": 9},
        "message": {"fields": [{"name": "x", "type": "u16", "default": 2}]},
    }
    path = tmp_path / "schema.json"
    path.write_text(json.dumps(data))
    schema = load_protocol_schema(path)
    assert schema.name == "jsonschema"
    assert schema.transport.port == 9
    assert schema.message.fields[0].default == 2


def test_load_protocol_schema_missing_fields_raises(tmp_path: Path):
    bad = {"name": "bad", "transport": {"type": "tcp", "host": "x", "port": 1}, "message": {"fields": []}}
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(bad))
    with pytest.raises(ValueError):
        load_protocol_schema(path)


def test_load_protocol_schema_yaml_requires_pyyaml(monkeypatch, tmp_path: Path):
    yaml_path = tmp_path / "s.yaml"
    yaml_path.write_text("name: demo\ntransport:\n  type: tcp\n  host: 1.1.1.1\n  port: 1\nmessage:\n  fields:\n    - name: x\n      type: u8\n")
    monkeypatch.setattr("fluxprobe.schema.yaml", None)
    with pytest.raises(RuntimeError):
        load_protocol_schema(yaml_path)


def test_parse_transport_defaults_when_missing():
    schema = protocol_from_dict(
        {
            "message": {"fields": [{"name": "x", "type": "u8", "default": 1}]},
            # host/port missing
        },
        default_name="missing",
    )
    assert schema.transport.host == "127.0.0.1"
    assert schema.transport.port == 0
