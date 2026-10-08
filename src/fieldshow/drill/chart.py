"""Place marchers from line, block, and arc shapes. See docs/ARCHITECTURE.md."""

from __future__ import annotations


def chart(show: dict) -> dict:
    raise NotImplementedError("drill agent owns chart()")


def interpolate(show: dict, beat: float) -> list[dict]:
    raise NotImplementedError("drill agent owns interpolate()")
