import random

import pytest

from fluxprobe.generator import (
    GeneratedMessage,
    _ensure_bytes,
    _int_bounds,
    _generate_field_value,
    generate_valid_message,
)
from fluxprobe.mutator import Mutator, _width_bytes
from fluxprobe.schema import protocol_from_dict


def build_simple_schema():
    return protocol_from_dict(
        {
            "name": "Simple",
            "transport": {"type": "tcp", "host": "x", "port": 1},
            "message": {
                "fields": [
                    {"name": "opcode", "type": "u8", "default": 1},
                    {"name": "length", "type": "u16", "length_of": "payload"},
                    {"name": "payload", "type": "bytes", "min_length": 1, "max_length": 4},
                ]
            },
        }
    )


def test_generate_valid_message_sets_length_field():
    schema = build_simple_schema()
    rng = random.Random(123)
    msg: GeneratedMessage = generate_valid_message(schema, rng)
    payload_len = msg.values["length"]
    assert payload_len == len(msg.values["payload"])
    # field_spans map should include all fields
    assert set(msg.field_spans) == {"opcode", "length", "payload"}
    min_v, max_v = _int_bounds(schema.message.fields[0])
    assert min_v == 0 and max_v == 0xFF


def test_mutator_operates_on_message():
    schema = build_simple_schema()
    rng = random.Random(456)
    msg = generate_valid_message(schema, rng)
    m = Mutator(schema)
    mutated = m.mutate(msg, rng, operations=3)
    assert isinstance(mutated, bytes)
    # Mutated payload can be shorter/longer; just ensure not equal most of the time with seeded RNG
    assert mutated != msg.data


def test_ensure_bytes_handles_int_and_str():
    field_int = build_simple_schema().message.fields[0]
    assert _ensure_bytes(5, field_int) == b"\x05"
    field_bytes = build_simple_schema().message.fields[2]
    assert _ensure_bytes("ABC", field_bytes).startswith(b"A")


def test_mutator_primitives_direct_calls():
    base_schema = build_simple_schema()
    enum_schema = protocol_from_dict(
        {
            "name": "Enum",
            "transport": {"type": "tcp", "host": "x", "port": 1},
            "message": {
                "fields": [
                    {"name": "kind", "type": "enum", "choices": [1, 2, 3], "default": 1},
                    {"name": "payload", "type": "bytes", "min_length": 1, "max_length": 2},
                ]
            },
        }
    )
    msg = generate_valid_message(base_schema, random.Random(1))
    m = Mutator(enum_schema)
    msg_enum = generate_valid_message(enum_schema, random.Random(2))
    buf_enum = bytearray(msg_enum.data)
    m._invalid_enum(buf_enum, msg_enum, random.Random(7))

    buf = bytearray(msg.data)
    m._bit_flip(buf, msg, random.Random(2))
    m._random_byte(buf, msg, random.Random(3))
    m._truncate(buf, msg, random.Random(4))
    m._extend(buf, msg, random.Random(5))
    m._corrupt_length(buf, msg, random.Random(6))
    assert isinstance(bytes(buf), bytes)


def test_generate_field_value_respects_bounds():
    field = build_simple_schema().message.fields[0]
    field.min_value = 2
    field.max_value = 2
    val = _generate_field_value(field, random.Random(8))
    assert val == 2


def test_generate_field_value_invalid_type_raises():
    field = protocol_from_dict(
        {
            "transport": {"type": "tcp", "host": "x", "port": 1},
            "message": {"fields": [{"name": "x", "type": "weird"}]},
        }
    ).message.fields[0]
    with pytest.raises(ValueError):
        _generate_field_value(field, random.Random(0))


def test_width_bytes_helper():
    schema = build_simple_schema()
    fields = schema.message.fields
    assert _width_bytes(fields[0]) == 1
    fields[1].type = "u16"
    assert _width_bytes(fields[1]) == 2


def test_generate_field_value_prefers_fuzz_values_when_allowed():
    schema = build_simple_schema()
    field = schema.message.fields[2]
    field.fuzz_values = [b"X"]

    class FixedRandom(random.Random):
        def random(self):
            return 0.0  # trigger fuzz_values path

    rng = FixedRandom()
    val = _generate_field_value(field, rng)
    assert val == b"X"


def test_corrupt_length_overflow_handles_exception():
    schema = protocol_from_dict(
        {
            "name": "Overflow",
            "transport": {"type": "tcp", "host": "x", "port": 1},
            "message": {
                "fields": [
                    {"name": "len", "type": "u8", "length_of": "payload"},
                    {"name": "payload", "type": "bytes", "min_length": 1, "max_length": 1},
                ]
            },
        }
    )
    msg = generate_valid_message(schema, random.Random(0))

    class MaxChoiceRandom(random.Random):
        def choice(self, seq):
            return seq[-1]

        def randrange(self, *args, **kwargs):
            return super().randrange(*args, **kwargs)

    m = Mutator(schema)
    buf = bytearray(msg.data)
    m._corrupt_length(buf, msg, MaxChoiceRandom())
    assert isinstance(bytes(buf), bytes)


def test_int_bounds_and_choices_and_length_handling():
    field_enum = protocol_from_dict(
        {
            "transport": {"type": "tcp", "host": "x", "port": 1},
            "message": {"fields": [{"name": "choice", "type": "enum", "choices": [5], "length": 1}]},
        }
    ).message.fields[0]
    assert _generate_field_value(field_enum, random.Random(0)) == 5
    field_u16 = protocol_from_dict(
        {
            "transport": {"type": "tcp", "host": "x", "port": 1},
            "message": {"fields": [{"name": "mid", "type": "u16"}]},
        }
    ).message.fields[0]
    assert _int_bounds(field_u16) == (0, 0xFFFF)
    field_u32 = protocol_from_dict(
        {
            "transport": {"type": "tcp", "host": "x", "port": 1},
            "message": {"fields": [{"name": "big", "type": "u32", "default": None}]},
        }
    ).message.fields[0]
    field_u32.min_value = 10
    field_u32.max_value = 10
    assert _int_bounds(field_u32) == (10, 10)
    assert _ensure_bytes(10, field_u32) == b"\x00\x00\x00\n"
    fixed_len_field = protocol_from_dict(
        {
            "transport": {"type": "tcp", "host": "x", "port": 1},
            "message": {"fields": [{"name": "fixed", "type": "bytes", "length": 2}]},
        }
    ).message.fields[0]
    val = _generate_field_value(fixed_len_field, random.Random(0))
    assert len(val) == 2


def test_generate_valid_message_length_of_numeric_field():
    schema = protocol_from_dict(
        {
            "name": "NumLen",
            "transport": {"type": "tcp", "host": "x", "port": 1},
            "message": {
                "fields": [
                    {"name": "value", "type": "u8", "default": 7},
                    {"name": "len_of_value", "type": "u16", "length_of": "value"},
                ]
            },
        }
    )
    msg = generate_valid_message(schema, random.Random(0))
    assert msg.values["len_of_value"] == 1


def test_mutator_short_buffers_and_missing_spans():
    schema = build_simple_schema()
    m = Mutator(schema)
    empty_msg = GeneratedMessage(data=b"", values={}, field_spans={})
    buf = bytearray()
    m._bit_flip(buf, empty_msg, random.Random(0))
    m._random_byte(buf, empty_msg, random.Random(0))
    m._truncate(buf, empty_msg, random.Random(0))
    # _invalid_enum should return when no enum fields/spans
    m._invalid_enum(buf, empty_msg, random.Random(0))
    enum_schema = protocol_from_dict(
        {
            "transport": {"type": "tcp", "host": "x", "port": 1},
            "message": {"fields": [{"name": "kind", "type": "enum", "choices": [1]}]},
        }
    )
    m_enum = Mutator(enum_schema)
    msg_missing_span = GeneratedMessage(data=b"\x01", values={}, field_spans={})
    m_enum._invalid_enum(bytearray(msg_missing_span.data), msg_missing_span, random.Random(0))


def test_corrupt_length_overflow_path():
    schema = protocol_from_dict(
        {
            "transport": {"type": "tcp", "host": "x", "port": 1},
            "message": {
                "fields": [
                    {"name": "len", "type": "u8", "length_of": "payload"},
                    {"name": "payload", "type": "bytes"},
                ]
            },
        }
    )
    msg = GeneratedMessage(data=b"\xFF", values={}, field_spans={"len": (0, 1)})

    class ChoiceLast(random.Random):
        def choice(self, seq):
            return seq[-1]

        def randrange(self, *args, **kwargs):
            return 0

    m = Mutator(schema)
    buf = bytearray(msg.data)
    m._corrupt_length(buf, msg, ChoiceLast())
    assert isinstance(bytes(buf), bytes)
