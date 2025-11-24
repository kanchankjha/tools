from typing import Dict

from .schema import ProtocolSchema, protocol_from_dict


BUILTIN_SCHEMAS: Dict[str, Dict] = {
    "echo": {
        "name": "Echo Demo",
        "transport": {"type": "tcp", "host": "127.0.0.1", "port": 9000, "timeout": 1.0},
        "message": {
            "fields": [
                {"name": "opcode", "type": "enum", "choices": [1, 2, 255], "default": 1},
                {"name": "payload_length", "type": "u16", "length_of": "payload"},
                {"name": "payload", "type": "bytes", "min_length": 0, "max_length": 24, "fuzz_values": ["", "HELLO", "DEADBEEF"]},
            ]
        },
    },
    "http": {
        "name": "HTTP Request",
        "transport": {"type": "tcp", "host": "127.0.0.1", "port": 80, "timeout": 1.0},
        "message": {
            "fields": [
                {"name": "method", "type": "string", "choices": ["GET", "POST", "PUT", "DELETE", "HEAD"]},
                {"name": "space1", "type": "string", "default": " "},
                {
                    "name": "path",
                    "type": "string",
                    "min_length": 1,
                    "max_length": 40,
                    "fuzz_values": ["/", "/index.html", "/../../etc/passwd", "/%00", "/very/long/path/component"],
                },
                {"name": "space2", "type": "string", "default": " "},
                {"name": "version", "type": "string", "choices": ["HTTP/1.1", "HTTP/1.0"], "default": "HTTP/1.1"},
                {"name": "crlf", "type": "string", "default": "\r\n"},
                {
                    "name": "headers",
                    "type": "string",
                    "min_length": 0,
                    "max_length": 200,
                    "fuzz_values": [
                        "Host: example.com\r\nUser-Agent: FluxProbe\r\n",
                        "Host:\r\n",
                        "Host: example.com\r\nContent-Length: 0\r\nX-Test: A\r\n",
                        "",
                    ],
                },
                {"name": "end", "type": "string", "default": "\r\n"},
            ]
        },
    },
    "dns": {
        "name": "DNS Query",
        "transport": {"type": "udp", "host": "8.8.8.8", "port": 53, "timeout": 1.0},
        "message": {
            "fields": [
                {"name": "transaction_id", "type": "u16"},
                {"name": "flags", "type": "u16", "default": 0x0100},
                {"name": "qdcount", "type": "u16", "default": 1},
                {"name": "ancount", "type": "u16", "default": 0},
                {"name": "nscount", "type": "u16", "default": 0},
                {"name": "arcount", "type": "u16", "default": 0},
                {"name": "qname", "type": "bytes", "min_length": 4, "max_length": 40, "fuzz_values": ["\x03www\x07example\x03com\x00", "\x01a\x01b\x01c\x00", "\x00"]},
                {"name": "qtype", "type": "u16", "choices": [1, 2, 5, 15, 16, 28, 252], "default": 1},
                {"name": "qclass", "type": "u16", "choices": [1, 3, 4, 254, 255], "default": 1},
            ]
        },
    },
    "mqtt": {
        "name": "MQTT Connect",
        "transport": {"type": "tcp", "host": "127.0.0.1", "port": 1883, "timeout": 1.0},
        "message": {
            "fields": [
                {"name": "packet_type", "type": "u8", "default": 0x10},
                {"name": "remaining_length", "type": "u16", "length_of": "payload"},
                {"name": "protocol_name", "type": "string", "default": "MQTT"},
                {"name": "protocol_level", "type": "u8", "default": 4},
                {"name": "connect_flags", "type": "u8", "default": 0x02},
                {"name": "keep_alive", "type": "u16", "default": 60},
                {"name": "client_id_length", "type": "u16", "length_of": "client_id"},
                {"name": "client_id", "type": "string", "min_length": 0, "max_length": 24, "fuzz_values": ["client-1", "", "A"*23, "null\x00id"]},
                {"name": "payload", "type": "bytes", "min_length": 0, "max_length": 32, "fuzz_values": ["", "test", "username\x00password"]},
            ]
        },
    },
    "modbus": {
        "name": "Modbus TCP",
        "transport": {"type": "tcp", "host": "127.0.0.1", "port": 502, "timeout": 1.0},
        "message": {
            "fields": [
                {"name": "transaction_id", "type": "u16"},
                {"name": "protocol_id", "type": "u16", "default": 0},
                {"name": "length", "type": "u16", "length_of": "payload"},
                {"name": "unit_id", "type": "u8", "default": 1},
                {"name": "function_code", "type": "enum", "choices": [1, 2, 3, 4, 5, 6, 15, 16], "default": 3},
                {"name": "payload", "type": "bytes", "min_length": 0, "max_length": 252, "fuzz_values": ["\x00\x6B\x00\x03", "\x00\x00\x00\x10", ""]},
            ]
        },
    },
    "coap": {
        "name": "CoAP GET",
        "transport": {"type": "udp", "host": "127.0.0.1", "port": 5683, "timeout": 1.0},
        "message": {
            "fields": [
                {"name": "ver_t_tkl", "type": "u8", "default": 0x40},
                {"name": "code", "type": "enum", "choices": [1, 2, 3, 132], "default": 1},
                {"name": "message_id", "type": "u16"},
                {"name": "token", "type": "bytes", "min_length": 0, "max_length": 8, "fuzz_values": ["", "\x01", "\xAA\xBB\xCC\xDD"]},
                {"name": "options", "type": "bytes", "min_length": 0, "max_length": 24, "fuzz_values": ["\xb6\x76\x65\x72\x73", "\xb2id", ""]},
                {"name": "payload", "type": "bytes", "min_length": 0, "max_length": 32, "fuzz_values": ["", "test", "verylongpayloaddata"]},
            ]
        },
    },
    "tcp": {
        "name": "TCP Raw Payload",
        "transport": {"type": "tcp", "host": "127.0.0.1", "port": 7, "timeout": 1.0},
        "message": {
            "fields": [
                {"name": "payload_length", "type": "u16", "length_of": "payload"},
                {"name": "payload", "type": "bytes", "min_length": 0, "max_length": 256, "fuzz_values": ["", "PING", "A"*32, "\x00\x00\x00\x00"]},
            ]
        },
    },
    "udp": {
        "name": "UDP Payload",
        "transport": {"type": "udp", "host": "127.0.0.1", "port": 9999, "timeout": 1.0},
        "message": {
            "fields": [
                {"name": "payload_length", "type": "u16", "length_of": "payload"},
                {"name": "payload", "type": "bytes", "min_length": 0, "max_length": 256, "fuzz_values": ["", "HELLO", "\xFF"*8, "B"*64]},
            ]
        },
    },
    "ip": {
        "name": "IPv4 Packet",
        "transport": {"type": "udp", "host": "127.0.0.1", "port": 0, "timeout": 1.0},
        "message": {
            "fields": [
                {"name": "version_ihl", "type": "u8", "default": 0x45},
                {"name": "dscp_ecn", "type": "u8", "default": 0x00},
                {"name": "total_length", "type": "u16", "min_value": 20, "max_value": 1500},
                {"name": "identification", "type": "u16"},
                {"name": "flags_fragment", "type": "u16", "default": 0x4000},
                {"name": "ttl", "type": "u8", "default": 64},
                {"name": "protocol", "type": "u8", "choices": [1, 6, 17, 41], "default": 6},
                {"name": "header_checksum", "type": "u16", "fuzz_values": [0x0000, 0xFFFF], "default": 0},
                {"name": "src_ip", "type": "bytes", "length": 4, "fuzz_values": ["\x7F\x00\x00\x01", "\xC0\xA8\x01\x01"], "default": "\x7F\x00\x00\x01"},
                {"name": "dst_ip", "type": "bytes", "length": 4, "fuzz_values": ["\x7F\x00\x00\x01", "\x08\x08\x08\x08"], "default": "\x7F\x00\x00\x01"},
                {"name": "payload", "type": "bytes", "min_length": 0, "max_length": 1480, "fuzz_values": ["", "DATA", "\xFF"*16]},
            ]
        },
    },
    "snmp": {
        "name": "SNMPv2c Get",
        "transport": {"type": "udp", "host": "127.0.0.1", "port": 161, "timeout": 1.0},
        "message": {
            "fields": [
                {"name": "pdu", "type": "bytes", "min_length": 8, "max_length": 200, "fuzz_values": ["\x30\x26\x02\x01\x01\x04\x06public\xa0\x19\x02\x04\x00\x00\x00\x01\x02\x01\x00\x02\x01\x00\x30\x0b\x30\x09\x06\x05\x2b\x06\x01\x02\x01\x05\x00", "\x30\x10\x02\x01\x01\x04\x06public\xa0\x05\x02\x01\x01\x30\x00", ""]},
            ]
        },
    },
    "ssh": {
        "name": "SSH KEXINIT",
        "transport": {"type": "tcp", "host": "127.0.0.1", "port": 22, "timeout": 1.0},
        "message": {
            "fields": [
                {"name": "packet_length", "type": "u32", "min_value": 0, "max_value": 4096},
                {"name": "padding_length", "type": "u8", "min_value": 4, "max_value": 32},
                {"name": "payload", "type": "bytes", "min_length": 0, "max_length": 4000, "fuzz_values": ["SSH-2.0-FluxProbe\r\n", "\x14\x00\x00\x00\x0b", ""]},
            ]
        },
    },
}


def load_profile(name: str) -> ProtocolSchema:
    key = name.lower()
    if key not in BUILTIN_SCHEMAS:
        raise ValueError(f"Unknown protocol profile '{name}'. Available: {', '.join(sorted(BUILTIN_SCHEMAS))}")
    return protocol_from_dict(BUILTIN_SCHEMAS[key], default_name=key)
