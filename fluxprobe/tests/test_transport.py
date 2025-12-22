from typing import Tuple

import pytest

from fluxprobe import transport


class DummySocket:
    def __init__(self):
        self.sent = []
        self.timeout = None
        self.closed = False
        self.addr = None
        self.connected = None

    def settimeout(self, value):
        self.timeout = value

    def connect(self, addr):
        self.connected = addr

    def sendall(self, data):
        self.sent.append(data)

    def sendto(self, data, addr: Tuple[str, int]):
        self.sent.append((data, addr))
        self.addr = addr

    def recv(self, bufsize=4096):
        return b"pong"

    def recvfrom(self, bufsize=4096):
        return (b"pong", ("1.1.1.1", 1))

    def recv_timeout(self, bufsize=4096):
        raise transport.socket.timeout()

    def close(self):
        self.closed = True


def test_tcp_transport(monkeypatch):
    dummy = DummySocket()
    monkeypatch.setattr(transport.socket, "getaddrinfo", lambda host, port, family, socktype: [(transport.socket.AF_INET, socktype, 0, "", ("127.0.0.1", 9999))])
    monkeypatch.setattr(transport.socket, "socket", lambda family, socktype, proto=0: dummy)
    t = transport.TCPTransport("127.0.0.1", 9999, timeout=0.1)
    t.send(b"ping")
    assert dummy.sent == [b"ping"]
    assert t.recv() == b"pong"
    t.close()
    assert dummy.closed
    assert dummy.connected == ("127.0.0.1", 9999)


def test_udp_transport(monkeypatch):
    dummy = DummySocket()
    monkeypatch.setattr(transport.socket, "getaddrinfo", lambda host, port, family, socktype: [(transport.socket.AF_INET, socktype, 0, "", ("127.0.0.1", 9999))])
    monkeypatch.setattr(transport.socket, "socket", lambda *args, **kwargs: dummy)
    t = transport.UDPTransport("127.0.0.1", 9999, timeout=0.1)
    t.send(b"data")
    assert dummy.addr == ("127.0.0.1", 9999)
    assert t.recv() == b"pong"
    t.close()
    assert dummy.closed


def test_transports_timeout(monkeypatch):
    dummy_tcp = DummySocket()
    monkeypatch.setattr(dummy_tcp, "recv", dummy_tcp.recv_timeout)
    monkeypatch.setattr(transport.socket, "getaddrinfo", lambda host, port, family, socktype: [(transport.socket.AF_INET, socktype, 0, "", ("127.0.0.1", 9999))])
    monkeypatch.setattr(transport.socket, "socket", lambda *args, **kwargs: dummy_tcp)
    t_tcp = transport.TCPTransport("127.0.0.1", 9999, timeout=0.1)
    assert t_tcp.recv(timeout=0.2) == b""

    dummy_udp = DummySocket()
    monkeypatch.setattr(dummy_udp, "recvfrom", dummy_udp.recv_timeout)
    monkeypatch.setattr(transport.socket, "getaddrinfo", lambda host, port, family, socktype: [(transport.socket.AF_INET, socktype, 0, "", ("127.0.0.1", 9999))])
    monkeypatch.setattr(transport.socket, "socket", lambda *args, **kwargs: dummy_udp)
    t_udp = transport.UDPTransport("127.0.0.1", 9999, timeout=0.1)
    assert t_udp.recv(timeout=0.2) == b""

    # Close paths that raise OSError should be swallowed.
    def raise_close():
        raise OSError("boom")

    dummy_tcp.close = raise_close
    dummy_udp.close = raise_close
    t_tcp.close()
    t_udp.close()


def test_create_transport_unknown():
    with pytest.raises(ValueError):
        transport.create_transport(transport.TransportSpec(type="unknown", host="h", port=1))


def test_create_transport_factory(monkeypatch):
    dummy = DummySocket()
    monkeypatch.setattr(transport.socket, "getaddrinfo", lambda host, port, family, socktype: [(transport.socket.AF_INET, socktype, 0, "", ("127.0.0.1", 1))])
    monkeypatch.setattr(transport.socket, "socket", lambda *args, **kwargs: dummy)
    t_tcp = transport.create_transport(transport.TransportSpec(type="tcp", host="h", port=1))
    assert isinstance(t_tcp, transport.TCPTransport)

    dummy_udp = DummySocket()
    monkeypatch.setattr(transport.socket, "getaddrinfo", lambda host, port, family, socktype: [(transport.socket.AF_INET, socktype, 0, "", ("127.0.0.1", 1))])
    monkeypatch.setattr(transport.socket, "socket", lambda *args, **kwargs: dummy_udp)
    t_udp = transport.create_transport(transport.TransportSpec(type="udp", host="h", port=1))
    assert isinstance(t_udp, transport.UDPTransport)


def test_udp_transport_ipv6(monkeypatch):
    dummy = DummySocket()
    monkeypatch.setattr(transport.socket, "getaddrinfo", lambda host, port, family, socktype: [(transport.socket.AF_INET6, socktype, 0, "", ("::1", 9999, 0, 0))])
    monkeypatch.setattr(transport.socket, "socket", lambda *args, **kwargs: dummy)
    t = transport.UDPTransport("::1", 9999, timeout=0.1)
    t.send(b"data")
    assert dummy.addr == ("::1", 9999, 0, 0)
    t.close()
