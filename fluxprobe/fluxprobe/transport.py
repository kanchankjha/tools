import logging
import socket
from typing import Optional

from .schema import TransportSpec

log = logging.getLogger(__name__)


class Transport:
    def send(self, data: bytes) -> None:  # pragma: no cover - interface
        raise NotImplementedError

    def recv(self, bufsize: int = 4096, timeout: Optional[float] = None) -> bytes:  # pragma: no cover - interface
        raise NotImplementedError

    def close(self) -> None:  # pragma: no cover - interface
        raise NotImplementedError


class TCPTransport(Transport):
    def __init__(self, host: str, port: int, timeout: float = 1.0) -> None:
        family, socktype, proto, sockaddr = _resolve_address(host, port, socket.SOCK_STREAM)
        self.sock = socket.socket(family, socktype, proto)
        self.sock.settimeout(timeout)
        self.sock.connect(sockaddr)

    def send(self, data: bytes) -> None:
        self.sock.sendall(data)

    def recv(self, bufsize: int = 4096, timeout: Optional[float] = None) -> bytes:
        if timeout is not None:
            self.sock.settimeout(timeout)
        try:
            return self.sock.recv(bufsize)
        except socket.timeout:
            return b""

    def close(self) -> None:
        try:
            self.sock.close()
        except OSError:
            pass


class UDPTransport(Transport):
    def __init__(self, host: str, port: int, timeout: float = 1.0) -> None:
        family, socktype, proto, sockaddr = _resolve_address(host, port, socket.SOCK_DGRAM)
        self.addr = sockaddr
        self.sock = socket.socket(family, socktype, proto)
        self.sock.settimeout(timeout)

    def send(self, data: bytes) -> None:
        self.sock.sendto(data, self.addr)

    def recv(self, bufsize: int = 4096, timeout: Optional[float] = None) -> bytes:
        if timeout is not None:
            self.sock.settimeout(timeout)
        try:
            packet, _ = self.sock.recvfrom(bufsize)
            return packet
        except socket.timeout:
            return b""

    def close(self) -> None:
        try:
            self.sock.close()
        except OSError:
            pass


def create_transport(spec: TransportSpec) -> Transport:
    if spec.type == "tcp":
        return TCPTransport(spec.host, spec.port, spec.timeout)
    if spec.type == "udp":
        return UDPTransport(spec.host, spec.port, spec.timeout)
    raise ValueError(f"Unsupported transport type: {spec.type}")


def _resolve_address(host: str, port: int, socktype: int) -> tuple[int, int, int, tuple]:
    infos = socket.getaddrinfo(host, port, 0, socktype)
    if not infos:
        raise ValueError(f"Unable to resolve address for {host}:{port}")
    family, socktype, proto, _, sockaddr = infos[0]
    return family, socktype, proto, sockaddr
