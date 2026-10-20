"""Stdlib-only immutable photo result and fixed byte/dimension limits."""
from dataclasses import dataclass

MAX_INPUT_BYTES = 8 * 1024 * 1024
MAX_PIXELS = 12_000_000
MAX_SIDE = 6000
OUTPUT_SIDE = 1600
MAX_OUTPUT_BYTES = 2 * 1024 * 1024


@dataclass(frozen=True)
class NormalizedPhoto:
    data: bytes
    sha256: str
    width: int
    height: int
    source_format: str
    content_type: str = 'image/jpeg'

