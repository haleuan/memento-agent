"""Standard-library identifiers used by persisted Memento records."""

import secrets
import time

_ULID_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def generate_record_id(prefix: str) -> str:
    """Generate a type-prefixed ULID record identifier.

    Args:
        prefix: Lowercase record type prefix, such as `ach`.

    Returns:
        A record identifier in the form `<prefix>_<26-character ULID>`.
    """
    timestamp = time.time_ns() // 1_000_000
    random_bits = secrets.randbits(80)
    value = (timestamp << 80) | random_bits
    encoded = "".join(
        _ULID_ALPHABET[(value >> shift) & 0x1F] for shift in range(125, -1, -5)
    )
    return f"{prefix}_{encoded}"
