"""Optional visual design: uniform, flag, and a short palette."""

from __future__ import annotations

import copy
import re

_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


def apply_design(show: dict, design: dict) -> dict:
    palette = list(design.get("palette") or [])
    if not 2 <= len(palette) <= 6:
        raise ValueError("palette needs 2 to 6 hex colors")
    for color in palette:
        if not isinstance(color, str) or not _HEX.match(color):
            raise ValueError(f"bad color {color}")
    out = copy.deepcopy(show)
    out["design"] = {
        "uniform": str(design.get("uniform") or ""),
        "flag": str(design.get("flag") or ""),
        "palette": palette,
    }
    return out
