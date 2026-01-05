import logging
import random
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .generator import generate_valid_message
from .mutator import Mutator
from .schema import ProtocolSchema
from .transport import Transport, create_transport

log = logging.getLogger(__name__)


def _hexdump(data: bytes, width: int = 16, max_bytes: int = 64) -> str:
    truncated = data[:max_bytes]
    hex_str = " ".join(f"{b:02X}" for b in truncated)
    if len(data) > max_bytes:
        hex_str += f" ... ({len(data)} bytes total)"
    return hex_str


@dataclass
class FuzzConfig:
    iterations: int = 100
    mutation_rate: float = 0.3
    mutations_per_frame: int = 1
    recv_timeout: float = 0.0
    seed: Optional[int] = None
    delay_ms: int = 0
    log_file: Optional[Path] = None
    dry_run: bool = False


class FuzzRunner:
    def __init__(self, schema: ProtocolSchema, config: FuzzConfig) -> None:
        self.schema = schema
        self.config = config
        self.rng = random.Random(config.seed)
        self.mutator = Mutator(schema)
        self._log_fp = None
        if config.log_file:
            config.log_file.parent.mkdir(parents=True, exist_ok=True)
            self._log_fp = config.log_file.open("a", encoding="utf-8")

    def _log_line(self, line: str) -> None:
        log.info(line)
        if self._log_fp:
            self._log_fp.write(line + "\n")
            self._log_fp.flush()

    def run(self) -> None:
        transport: Optional[Transport] = None
        if not self.config.dry_run:
            transport = create_transport(self.schema.transport)
        self._log_line(f"Starting fuzz run against {self.schema.transport.host}:{self.schema.transport.port} "
                       f"({self.schema.transport.type}), iterations={self.config.iterations}, "
                       f"mutation_rate={self.config.mutation_rate}, seed={self.config.seed}, "
                       f"dry_run={self.config.dry_run}")
        try:
            for idx in range(1, self.config.iterations + 1):
                msg = generate_valid_message(self.schema, self.rng)
                payload = msg.data
                mutated = False
                if self.rng.random() < self.config.mutation_rate:
                    payload = self.mutator.mutate(msg, self.rng, operations=self.config.mutations_per_frame)
                    mutated = True

                if self.config.dry_run:
                    self._log_line(
                        f"[{idx}] {'M' if mutated else 'V'} DRY-RUN sent={len(payload)}B { _hexdump(payload) }"
                    )
                else:
                    assert transport is not None
                    transport.send(payload)
                    response = b""
                    if self.config.recv_timeout and self.config.recv_timeout > 0:
                        response = transport.recv(timeout=self.config.recv_timeout)
                    self._log_line(
                        f"[{idx}] {'M' if mutated else 'V'} sent={len(payload)}B { _hexdump(payload) } "
                        f"resp={len(response)}B { _hexdump(response) if response else ''}"
                    )
                if self.config.delay_ms:
                    time.sleep(self.config.delay_ms / 1000.0)
        finally:
            if transport:
                transport.close()
            if self._log_fp:
                self._log_fp.close()
                self._log_fp = None
