"""Additional tests for bug fixes and validation improvements."""
import pytest
from fluxprobe.schema import protocol_from_dict, _parse_transport
from fluxprobe.generator import generate_valid_message, _generate_field_value
from fluxprobe.mutator import Mutator, _width_bytes
import random


def test_length_of_validates_field_reference():
    """Test that length_of references are validated."""
    with pytest.raises(ValueError, match="no such field exists"):
        protocol_from_dict(
            {
                "transport": {"type": "tcp", "host": "x", "port": 1},
                "message": {
                    "fields": [
                        {"name": "len", "type": "u16", "length_of": "nonexistent"}
                    ]
                },
            }
        )


def test_port_validation():
    """Test that invalid port numbers are rejected."""
    with pytest.raises(ValueError, match="Invalid port"):
        _parse_transport({"type": "tcp", "host": "x", "port": 0})

    with pytest.raises(ValueError, match="Invalid port"):
        _parse_transport({"type": "tcp", "host": "x", "port": 70000})


def test_string_field_generates_strings():
    """Test that string type fields generate actual strings, not bytes."""
    schema = protocol_from_dict(
        {
            "transport": {"type": "tcp", "host": "x", "port": 1},
            "message": {
                "fields": [
                    {"name": "text", "type": "string", "min_length": 5, "max_length": 5}
                ]
            },
        }
    )
    rng = random.Random(42)
    msg = generate_valid_message(schema, rng)

    # Verify the value is a string
    assert isinstance(msg.values["text"], str)
    assert len(msg.values["text"]) == 5


def test_invalid_enum_handles_string_choices():
    """Test that _invalid_enum mutation handles string enum choices."""
    schema = protocol_from_dict(
        {
            "transport": {"type": "tcp", "host": "x", "port": 1},
            "message": {
                "fields": [
                    {
                        "name": "method",
                        "type": "enum",
                        "choices": ["GET", "POST", "PUT"],
                        "default": "GET",
                    }
                ]
            },
        }
    )
    rng = random.Random(123)
    msg = generate_valid_message(schema, rng)
    mutator = Mutator(schema)

    # Should not crash when mutating string enums
    mutated = mutator.mutate(msg, rng, operations=5)
    assert isinstance(mutated, bytes)


def test_enum_width_detection_from_choices():
    """Test that enum field width is correctly inferred from choices."""
    # u8 range enum
    field_u8 = protocol_from_dict(
        {
            "transport": {"type": "tcp", "host": "x", "port": 1},
            "message": {"fields": [{"name": "x", "type": "enum", "choices": [1, 2, 255]}]},
        }
    ).message.fields[0]
    assert _width_bytes(field_u8) == 1

    # u16 range enum
    field_u16 = protocol_from_dict(
        {
            "transport": {"type": "tcp", "host": "x", "port": 1},
            "message": {"fields": [{"name": "x", "type": "enum", "choices": [1, 256, 1000]}]},
        }
    ).message.fields[0]
    assert _width_bytes(field_u16) == 2

    # u32 range enum
    field_u32 = protocol_from_dict(
        {
            "transport": {"type": "tcp", "host": "x", "port": 1},
            "message": {"fields": [{"name": "x", "type": "enum", "choices": [1, 70000]}]},
        }
    ).message.fields[0]
    assert _width_bytes(field_u32) == 4


def test_corrupt_length_avoids_overflow():
    """Test that _corrupt_length doesn't overflow when doubling large values."""
    schema = protocol_from_dict(
        {
            "transport": {"type": "tcp", "host": "x", "port": 1},
            "message": {
                "fields": [
                    {"name": "len", "type": "u8", "length_of": "payload"},
                    {"name": "payload", "type": "bytes", "min_length": 1, "max_length": 1},
                ]
            },
        }
    )

    # Create a message with maximum u8 length value
    from fluxprobe.generator import GeneratedMessage
    msg = GeneratedMessage(
        data=b"\xFF\x41",
        values={"len": 255, "payload": b"A"},
        field_spans={"len": (0, 1), "payload": (1, 2)},
    )

    mutator = Mutator(schema)
    rng = random.Random(456)

    # Should not crash even with large current value
    buf = bytearray(msg.data)
    mutator._corrupt_length(buf, msg, rng)
    assert isinstance(bytes(buf), bytes)
def test_length_of_numeric_field_uses_proper_serialization():
    """Test that length_of correctly calculates length for numeric fields."""
    schema = protocol_from_dict(
        {
            "transport": {"type": "tcp", "host": "x", "port": 1},
            "message": {
                "fields": [
                    {"name": "value", "type": "u16", "default": 1234},
                    {"name": "len_of_value", "type": "u8", "length_of": "value"},
                ]
            },
        }
    )
    rng = random.Random(0)
    msg = generate_valid_message(schema, rng)

    # u16 serializes to 2 bytes
    assert msg.values["len_of_value"] == 2
    assert msg.data == b"\x04\xd2\x02"  # 1234 in big-endian (\x04\xd2) + length (\x02)
def test_hexdump_truncation_indication():
    """Test that hexdump indicates when data is truncated."""
    from fluxprobe.runner import _hexdump

    short_data = b"\x01\x02\x03"
    result = _hexdump(short_data)
    assert "..." not in result

    long_data = b"\x00" * 100
    result = _hexdump(long_data)
    assert "... (100 bytes total)" in result
    assert "00 00 00" in result  # Some data shown
def test_string_enum_with_fuzz_values():
    """Test that string enums work with fuzz_values."""
    schema = protocol_from_dict(
        {
            "transport": {"type": "tcp", "host": "x", "port": 1},
            "message": {
                "fields": [
                    {
                        "name": "method",
                        "type": "enum",
                        "choices": ["GET", "POST"],
                        "fuzz_values": ["INVALID", "X"],
                    }
                ]
            },
        }
    )
    rng = random.Random(0)
    msg = generate_valid_message(schema, rng)
    assert msg.values["method"] in ["GET", "POST", "INVALID", "X"]


def test_length_of_with_missing_target():
    """Test that length_of handles missing target field gracefully."""
    # This should be caught by validation, but test the generator behavior
    from fluxprobe.schema import FieldSpec, MessageSpec, TransportSpec, ProtocolSchema

    # Manually construct invalid schema (bypassing validation)
    fields = [
        FieldSpec(name="len", type="u16", length_of="missing"),
        FieldSpec(name="data", type="bytes", min_length=1, max_length=2),
    ]
    schema = ProtocolSchema(
        name="test",
        transport=TransportSpec(type="tcp", host="x", port=1),
        message=MessageSpec(fields=fields),
    )

    rng = random.Random(0)
    msg = generate_valid_message(schema, rng)

    # Should default to 0 when target field doesn't exist
    assert msg.values["len"] == 0
