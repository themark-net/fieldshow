"""MusicXML and MIDI writers and the MusicXML importer."""

from __future__ import annotations

from pathlib import Path


def export_musicxml(show: dict, path: str | Path) -> None:
    raise NotImplementedError("music agent owns export_musicxml()")


def export_midi(show: dict, path: str | Path) -> None:
    raise NotImplementedError("music agent owns export_midi()")


def import_musicxml(path: str | Path) -> dict:
    raise NotImplementedError("music agent owns import_musicxml()")
