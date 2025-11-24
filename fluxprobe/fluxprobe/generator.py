import logging
import struct
from dataclasses import dataclass
from typing import Dict, Tuple

from .schema import FieldSpec, ProtocolSchema

log = logging.getLogger(__name__)


@dataclass
class GeneratedMessage:
    data: bytes
    values: Dict[str, object]
    field_spans: Dict[str, Tuple[int, int]]


def _int_bounds(field: FieldSpec) -> Tuple[int, int]:
    if field.type == "u8" or (field.type == "enum" and (field.length or 1) == 1):
        default_max = 0xFF
    elif field.type == "u16" or (field.type == "enum" and (field.length or 2) == 2):
        default_max = 0xFFFF
    else:
        default_max = 0xFFFFFFFF
    min_v = 0 if field.min_value is None else int(field.min_value)
    max_v = default_max if field.max_value is None else int(field.max_value)
    return min_v, max_v


def _generate_field_value(field: FieldSpec, rng) -> object:
    if field.choices:
        return rng.choice(field.choices)

    if field.type in ("u8", "u16", "u32", "enum"):
        min_v, max_v = _int_bounds(field)
        return rng.randint(min_v, max_v)

    min_len = 0 if field.min_length is None else int(field.min_length)
    max_len = 32 if field.max_length is None else int(field.max_length)
    if field.length is not None:
        min_len = max_len = field.length

    if field.type in ("bytes", "string"):
        if field.fuzz_values and rng.random() < 0.3:
            candidate = rng.choice(field.fuzz_values)
            return candidate
        size = rng.randint(min_len, max_len)
        if field.type == "string":
            # Generate random ASCII/printable string
            return ''.join(chr(rng.randint(32, 126)) for _ in range(size))
        return rng.randbytes(size)

    raise ValueError(f"Unsupported field type: {field.type}")


def _ensure_bytes(value: object, field: FieldSpec) -> bytes:
    if isinstance(value, bytes):
        return value
    if isinstance(value, str):
        encoding = field.encoding or ("latin-1" if field.type == "bytes" else "ascii")
        return value.encode(encoding, errors="ignore")
    if isinstance(value, int):
        if field.type == "u8" or (field.type == "enum" and (field.length or 1) == 1):
            return struct.pack(">B", value & 0xFF)
        if field.type == "u16" or (field.type == "enum" and (field.length or 2) == 2):
            return struct.pack(">H", value & 0xFFFF)
        if field.type == "u32" or (field.type == "enum" and (field.length or 4) == 4):
            return struct.pack(">I", value & 0xFFFFFFFF)
    raise ValueError(f"Cannot convert value '{value}' for field {field.name}")


def generate_valid_message(schema: ProtocolSchema, rng) -> GeneratedMessage:
    values: Dict[str, object] = {}
    for field in schema.message.fields:
        if field.length_of:
            continue
        values[field.name] = field.default if field.default is not None else _generate_field_value(field, rng)

    # Fill derived length fields after main values exist.
    # Build field lookup map for efficiency
    field_map = {f.name: f for f in schema.message.fields}

    for field in schema.message.fields:
        if not field.length_of:
            continue
        target_field = field_map.get(field.length_of)
        if not target_field:
            values[field.name] = 0
            continue

        target_value = values.get(field.length_of, b"")
        # Convert to bytes using proper serialization to get accurate length
        target_bytes = _ensure_bytes(target_value, target_field)
        values[field.name] = len(target_bytes)

    buf = bytearray()
    field_spans: Dict[str, Tuple[int, int]] = {}
    for field in schema.message.fields:
        raw_value = values[field.name]
        field_bytes = _ensure_bytes(raw_value, field)
        start = len(buf)
        buf.extend(field_bytes)
        end = len(buf)
        field_spans[field.name] = (start, end)

    return GeneratedMessage(data=bytes(buf), values=values, field_spans=field_spans)
