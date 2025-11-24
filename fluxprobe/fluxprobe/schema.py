import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import yaml  # type: ignore
except ImportError:  # pragma: no cover - handled at runtime
    yaml = None

log = logging.getLogger(__name__)


@dataclass
class FieldSpec:
    name: str
    type: str
    length: Optional[int] = None
    length_of: Optional[str] = None
    min_value: Optional[int] = None
    max_value: Optional[int] = None
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    choices: Optional[List[Any]] = None
    default: Any = None
    encoding: str = "ascii"
    fuzz_values: List[Any] = field(default_factory=list)


@dataclass
class MessageSpec:
    fields: List[FieldSpec]


@dataclass
class TransportSpec:
    type: str
    host: str
    port: int
    timeout: float = 1.0


@dataclass
class ProtocolSchema:
    name: str
    transport: TransportSpec
    message: MessageSpec


def _parse_field(raw: Dict[str, Any]) -> FieldSpec:
    return FieldSpec(
        name=raw["name"],
        type=str(raw["type"]).lower(),
        length=raw.get("length"),
        length_of=raw.get("length_of"),
        min_value=raw.get("min_value"),
        max_value=raw.get("max_value"),
        min_length=raw.get("min_length"),
        max_length=raw.get("max_length"),
        choices=raw.get("choices"),
        default=raw.get("default"),
        encoding=raw.get("encoding", "ascii"),
        fuzz_values=raw.get("fuzz_values", []),
    )


def _parse_transport(raw: Dict[str, Any]) -> TransportSpec:
    if raw.get("port") is None:
        port = 0
    else:
        port = int(raw["port"])
        if not (0 < port <= 65535):
            raise ValueError(f"Invalid port number: {port}. Must be 1-65535")
    return TransportSpec(
        type=str(raw.get("type", "tcp")).lower(),
        host=raw.get("host", "127.0.0.1"),
        port=port,
        timeout=float(raw.get("timeout", 1.0)),
    )


def _parse_message(raw: Dict[str, Any]) -> MessageSpec:
    raw_fields = raw.get("fields", [])
    if not raw_fields:
        raise ValueError("message.fields is required in schema")
    fields = [_parse_field(f) for f in raw_fields]

    # Validate length_of references
    field_names = {f.name for f in fields}
    for field in fields:
        if field.length_of and field.length_of not in field_names:
            raise ValueError(
                f"Field '{field.name}' has length_of='{field.length_of}' "
                f"but no such field exists in schema"
            )

    # Detect circular dependencies in length_of chains
    def _has_cycle(field_name: str, visited: set, path: set) -> bool:
        """Detect cycles using DFS with path tracking."""
        if field_name in path:
            return True  # Cycle detected
        if field_name in visited:
            return False  # Already checked, no cycle from here

        visited.add(field_name)
        path.add(field_name)

        # Find field and check its length_of reference
        field = next((f for f in fields if f.name == field_name), None)
        if field and field.length_of:
            if _has_cycle(field.length_of, visited, path):
                return True

        path.remove(field_name)
        return False

    visited: set = set()
    for field in fields:
        if field.length_of and field.name not in visited:
            if _has_cycle(field.name, visited, set()):
                raise ValueError(
                    f"Circular dependency detected in length_of chain involving field '{field.name}'"
                )

    return MessageSpec(fields=fields)


def _load_raw(path: Path) -> Dict[str, Any]:
    text = path.read_text()
    if path.suffix.lower() in (".yaml", ".yml"):
        if yaml is None:
            raise RuntimeError("PyYAML is required to load YAML schemas. Install with `pip install PyYAML`.")
        return yaml.safe_load(text)
    return json.loads(text)


def load_protocol_schema(path: Path) -> ProtocolSchema:
    raw = _load_raw(path)
    schema = protocol_from_dict(raw, default_name=path.stem)
    log.debug("Loaded schema %s from %s", schema.name, path)
    return schema


def protocol_from_dict(raw: Dict[str, Any], default_name: Optional[str] = None) -> ProtocolSchema:
    name = raw.get("name", default_name or "unnamed")
    transport = _parse_transport(raw.get("transport", {}))
    message = _parse_message(raw["message"])
    return ProtocolSchema(name=name, transport=transport, message=message)
