import pytest

from fluxprobe.profiles import BUILTIN_SCHEMAS, load_profile


def test_builtin_profiles_present():
    # Ensure key profiles exist for simplified usage.
    required = {"echo", "http", "dns", "mqtt", "modbus", "coap", "tcp", "udp", "ip", "snmp", "ssh"}
    assert required.issubset(set(BUILTIN_SCHEMAS.keys()))


def test_load_profile_returns_schema():
    schema = load_profile("http")
    assert schema.name.lower().startswith("http")
    assert schema.transport.host == "127.0.0.1"
    assert schema.transport.port == 80


def test_load_profile_unknown_raises():
    with pytest.raises(ValueError):
        load_profile("not-a-protocol")
