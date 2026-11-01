"""Credential generation engine. Pure Python, no GUI dependencies.

All randomness comes from the ``secrets`` module (OS CSPRNG).
"""
from __future__ import annotations

import math
import secrets
import string
from dataclasses import dataclass

from .words import WORDS

MODES = ("password", "passphrase", "pin", "token")
MODE_LABELS = {
    "password": "Password",
    "passphrase": "Passphrase",
    "pin": "PIN",
    "token": "Access token",
}
LENGTH_RANGES = {  # (min, max) - characters, or words for passphrases
    "password": (8, 64),
    "passphrase": (3, 10),
    "pin": (4, 12),
    "token": (16, 64),
}
LENGTH_UNITS = {"password": "characters", "passphrase": "words", "pin": "digits", "token": "characters"}

DEFAULT_SYMBOLS = "!@#$%^&*()-_=+[]{};:,.?"
AMBIGUOUS = frozenset("O0oIl1|")
TOKEN_ALPHABET = string.ascii_letters + string.digits + "-_"
RATING_LABELS = ("Very weak", "Weak", "Fair", "Strong", "Excellent")
_RATING_THRESHOLDS = (28, 40, 60, 80)  # bits


@dataclass(frozen=True)
class Policy:
    """Describes what to generate. Immutable so profiles can't be mutated by the UI."""

    mode: str = "password"
    length: int = 16
    lower: bool = True
    upper: bool = True
    digits: bool = True
    symbols: bool = True
    symbol_set: str = DEFAULT_SYMBOLS
    avoid_ambiguous: bool = False
    separator: str = "-"
    capitalize: bool = True
    add_number: bool = True

    def validate(self) -> None:
        if self.mode not in MODES:
            raise ValueError(f"Unknown mode {self.mode!r}; expected one of {', '.join(MODES)}")
        lo, hi = LENGTH_RANGES[self.mode]
        if not lo <= self.length <= hi:
            raise ValueError(f"{MODE_LABELS[self.mode]} length must be {lo}-{hi} {LENGTH_UNITS[self.mode]}")
        if len(self.separator) > 3:
            raise ValueError("Separator may be at most 3 characters")
        if self.mode == "password" and not _pools(self):
            raise ValueError("Enable at least one character type")
        if self.mode == "password" and self.length < len(_pools(self)):
            raise ValueError("Length is too short for the selected character types")


@dataclass(frozen=True)
class GenerationResult:
    value: str
    entropy_bits: float

    @property
    def rating(self) -> int:
        """0 (very weak) .. 4 (excellent)."""
        return sum(self.entropy_bits >= t for t in _RATING_THRESHOLDS)

    @property
    def label(self) -> str:
        return RATING_LABELS[self.rating]


def _pools(p: Policy) -> list[str]:
    pools = []
    if p.lower:
        pools.append(string.ascii_lowercase)
    if p.upper:
        pools.append(string.ascii_uppercase)
    if p.digits:
        pools.append(string.digits)
    if p.symbols:
        pools.append(p.symbol_set)
    cleaned = []
    for pool in pools:
        if p.avoid_ambiguous:
            pool = "".join(c for c in pool if c not in AMBIGUOUS)
        pool = "".join(dict.fromkeys(pool))  # de-duplicate, keep order
        if pool:
            cleaned.append(pool)
    return cleaned


def _password(p: Policy) -> GenerationResult:
    pools = _pools(p)
    alphabet = "".join(dict.fromkeys("".join(pools)))
    chars = [secrets.choice(pool) for pool in pools]  # guarantee one of each enabled type
    chars += [secrets.choice(alphabet) for _ in range(p.length - len(chars))]
    secrets.SystemRandom().shuffle(chars)
    return GenerationResult("".join(chars), p.length * math.log2(len(alphabet)))


def _is_trivial_pin(pin: str) -> bool:
    if len(set(pin)) == 1:
        return True
    steps = {int(b) - int(a) for a, b in zip(pin, pin[1:])}
    return steps in ({1}, {-1})


def _pin(p: Policy) -> GenerationResult:
    while True:
        pin = "".join(secrets.choice(string.digits) for _ in range(p.length))
        if not _is_trivial_pin(pin):
            return GenerationResult(pin, p.length * math.log2(10))


def _token(p: Policy) -> GenerationResult:
    value = "".join(secrets.choice(TOKEN_ALPHABET) for _ in range(p.length))
    return GenerationResult(value, p.length * math.log2(len(TOKEN_ALPHABET)))


def _passphrase(p: Policy) -> GenerationResult:
    words = [secrets.choice(WORDS) for _ in range(p.length)]
    if p.capitalize:
        words = [w.capitalize() for w in words]
    value = p.separator.join(words)
    bits = p.length * math.log2(len(WORDS))
    if p.add_number:
        value += p.separator + f"{secrets.randbelow(100):02d}"
        bits += math.log2(100)
    return GenerationResult(value, bits)


_GENERATORS = {"password": _password, "passphrase": _passphrase, "pin": _pin, "token": _token}


def generate(policy: Policy) -> GenerationResult:
    """Generate one credential. Raises ValueError for an invalid policy."""
    policy.validate()
    return _GENERATORS[policy.mode](policy)


def soft_wrap(value: str, separator: str, width: int = 32) -> str:
    """Insert line breaks after separators so long passphrases wrap between words.

    Display-only: callers must copy the original ``value``, never the wrapped text.
    """
    if not separator or separator not in value:
        return value
    parts = value.split(separator)
    lines, cur = [], ""
    for i, part in enumerate(parts):
        piece = part + (separator if i < len(parts) - 1 else "")
        if cur and len(cur) + len(piece) > width:
            lines.append(cur)
            cur = ""
        cur += piece
    lines.append(cur)
    return "\n".join(lines)
