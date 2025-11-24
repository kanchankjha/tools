import logging
import struct
from typing import List, Optional

from .generator import GeneratedMessage
from .schema import FieldSpec, ProtocolSchema

log = logging.getLogger(__name__)


def _width_bytes(field: FieldSpec) -> int:
    if field.type == "u8":
        return 1
    if field.type == "u16":
        return 2
    if field.type == "u32":
        return 4
    if field.type == "enum":
        # Use explicit length if provided, otherwise infer from choices
        if field.length:
            return field.length
        if field.choices:
            int_choices = [c for c in field.choices if isinstance(c, int)]
            if int_choices:
                max_choice = max(int_choices)
                if max_choice <= 0xFF:
                    return 1
                elif max_choice <= 0xFFFF:
                    return 2
                else:
                    return 4
        return 1  # default
    return 4  # default for unknown types


class Mutator:
    def __init__(self, schema: ProtocolSchema):
        self.schema = schema
        self.length_fields: List[FieldSpec] = [f for f in schema.message.fields if f.length_of]
        self.enum_fields: List[FieldSpec] = [f for f in schema.message.fields if f.type == "enum"]

    def mutate(self, msg: GeneratedMessage, rng, operations: int = 1) -> bytes:
        buf = bytearray(msg.data)
        for _ in range(max(1, operations)):
            choice = rng.choice(
                [
                    self._bit_flip,
                    self._random_byte,
                    self._truncate,
                    self._extend,
                    self._corrupt_length,
                    self._invalid_enum,
                ]
            )
            choice(buf, msg, rng)
        return bytes(buf)

    def _bit_flip(self, buf: bytearray, msg: GeneratedMessage, rng) -> None:
        if not buf:
            return
        idx = rng.randrange(len(buf))
        bit = 1 << rng.randrange(8)
        buf[idx] ^= bit

    def _random_byte(self, buf: bytearray, msg: GeneratedMessage, rng) -> None:
        if not buf:
            return
        idx = rng.randrange(len(buf))
        buf[idx] = rng.randrange(256)

    def _truncate(self, buf: bytearray, msg: GeneratedMessage, rng) -> None:
        if len(buf) <= 1:
            return
        new_len = rng.randrange(1, len(buf))
        del buf[new_len:]

    def _extend(self, buf: bytearray, msg: GeneratedMessage, rng) -> None:
        extra_len = rng.randint(1, 8)
        buf.extend(rng.randbytes(extra_len))

    def _corrupt_length(self, buf: bytearray, msg: GeneratedMessage, rng) -> None:
        if not self.length_fields or not msg.field_spans:
            return
        field = rng.choice(self.length_fields)
        span = msg.field_spans.get(field.name)
        if not span:
            return
        start, end = span
        width = _width_bytes(field)
        current = int.from_bytes(buf[start:end], "big")
        max_value = (2 ** (8 * width)) - 1

        # Build offset choices, avoiding overflow
        offset_choices = [-2, -1, 1, 2]
        if current < max_value // 2:
            offset_choices.append(current * 2 + 1)

        offset = rng.choice(offset_choices)
        corrupt_value = max(0, current + offset)
        try:
            buf[start:end] = corrupt_value.to_bytes(width, "big")
        except OverflowError:
            buf[start:end] = (0).to_bytes(width, "big")

    def _invalid_enum(self, buf: bytearray, msg: GeneratedMessage, rng) -> None:
        if not self.enum_fields or not msg.field_spans:
            return
        field = rng.choice(self.enum_fields)
        span = msg.field_spans.get(field.name)
        if not span:
            return
        start, end = span
        width = _width_bytes(field)
        choices = field.choices or []

        # Only mutate if we have integer choices
        int_choices = [c for c in choices if isinstance(c, int)]
        if not int_choices:
            # For string enums, inject invalid bytes
            buf[start:end] = rng.randbytes(width)
            return

        max_choice = max(int_choices)
        invalid_value = max_choice + rng.randint(1, 10)
        try:
            buf[start:end] = invalid_value.to_bytes(width, "big", signed=False)
        except OverflowError:
            buf[start:end] = ((2 ** (8 * width)) - 1).to_bytes(width, "big")
