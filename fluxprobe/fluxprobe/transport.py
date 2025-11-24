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
        self.sock = socket.create_connection((host, port), timeout=timeout)
        self.sock.settimeout(timeout)

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
        self.addr = (host, port)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
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
