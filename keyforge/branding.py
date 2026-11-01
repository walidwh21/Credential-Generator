"""Shared drawing helpers so the GUI and preview renderer use identical geometry.

The logo is a generic padlock drawn from primitives - there is no binary asset
and therefore no embedded image metadata.
"""
from __future__ import annotations


def shade(hex_color: str, factor: float) -> str:
    """Lighten (factor > 1 blends toward white) or darken (factor < 1) a #rrggbb colour."""
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    if factor <= 1:
        r, g, b = (int(c * factor) for c in (r, g, b))
    else:
        t = min(factor - 1, 1)
        r, g, b = (int(c + (255 - c) * t) for c in (r, g, b))
    return f"#{r:02x}{g:02x}{b:02x}"


def lock_shapes(cx: float, cy: float, s: float) -> list[tuple]:
    """Primitives for a padlock centred on (cx, cy) with nominal size s.

    Each tuple starts with a kind: 'arc_top' | 'line' | 'rrect' | 'oval' | 'rect',
    and ends with a colour role: 'accent' (the brand colour) or 'bg' (cut-outs).
    """
    sw = 0.09 * s                                    # shackle stroke width
    return [
        ("arc_top", (cx - 0.22 * s, cy - 0.45 * s, cx + 0.22 * s, cy - 0.01 * s), sw, "accent"),
        ("line", (cx - 0.22 * s, cy - 0.23 * s, cx - 0.22 * s, cy + 0.02 * s), sw, "accent"),
        ("line", (cx + 0.22 * s, cy - 0.23 * s, cx + 0.22 * s, cy + 0.02 * s), sw, "accent"),
        ("rrect", (cx - 0.35 * s, cy - 0.05 * s, cx + 0.35 * s, cy + 0.45 * s), 0.08 * s, "accent"),
        ("oval", (cx - 0.06 * s, cy + 0.08 * s, cx + 0.06 * s, cy + 0.20 * s), "bg"),
        ("rect", (cx - 0.025 * s, cy + 0.16 * s, cx + 0.025 * s, cy + 0.31 * s), "bg"),
    ]
