"""Export a charted show to an OpenMarch .om document."""

from __future__ import annotations

from pathlib import Path


def export_om(show: dict) -> dict:
    raise NotImplementedError("drill agent owns export_om()")


def write_om(show: dict, path: str | Path) -> None:
    raise NotImplementedError("drill agent owns write_om()")
