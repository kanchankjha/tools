"""Test for circular dependency detection in length_of fields."""
import pytest
from fluxprobe.schema import protocol_from_dict


def test_circular_length_of_dependency_direct():
    """Test that direct circular length_of dependencies are caught."""
    # Field A's length depends on field B, field B's length depends on field A
    with pytest.raises(ValueError, match="[Cc]ircular"):
        protocol_from_dict(
            {
                "transport": {"type": "tcp", "host": "x", "port": 1},
                "message": {
                    "fields": [
                        {"name": "len_a", "type": "u16", "length_of": "len_b"},
                        {"name": "len_b", "type": "u16", "length_of": "len_a"},
                    ]
                },
            }
        )


def test_circular_length_of_dependency_indirect():
    """Test that indirect circular length_of dependencies are caught."""
    # A -> B -> C -> A (three-way cycle)
    with pytest.raises(ValueError, match="[Cc]ircular"):
        protocol_from_dict(
            {
                "transport": {"type": "tcp", "host": "x", "port": 1},
                "message": {
                    "fields": [
                        {"name": "len_a", "type": "u16", "length_of": "len_b"},
                        {"name": "len_b", "type": "u16", "length_of": "len_c"},
                        {"name": "len_c", "type": "u16", "length_of": "len_a"},
                    ]
                },
            }
        )


def test_length_of_self_reference():
    """Test that self-referencing length_of is caught."""
    with pytest.raises(ValueError, match="[Cc]ircular"):
        protocol_from_dict(
            {
                "transport": {"type": "tcp", "host": "x", "port": 1},
                "message": {
                    "fields": [
                        {"name": "len", "type": "u16", "length_of": "len"},
                    ]
                },
            }
        )


def test_valid_length_of_chain():
    """Test that valid non-circular length_of chains work."""
    # This is valid: len_a -> data (no cycle)
    schema = protocol_from_dict(
        {
            "transport": {"type": "tcp", "host": "x", "port": 1},
            "message": {
                "fields": [
                    {"name": "len_a", "type": "u16", "length_of": "data"},
                    {"name": "data", "type": "bytes", "min_length": 0, "max_length": 10},
                ]
            },
        }
    )
    assert schema.name == "unnamed"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
