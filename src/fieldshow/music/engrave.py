"""Engrave one PDF per part. LilyPond is the engraver (ADR 0004)."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from fieldshow.model import SECTION_ORDER
from fieldshow.music.io import export_musicxml

# Printed when the binary is missing. build still exits 0.
MISSING_ENGRAVER = "PDF parts unavailable: LilyPond not found (set FIELDSHOW_ENGRAVER)"
MISSING_CONVERTER = "PDF parts unavailable: musicxml2ly not found (set FIELDSHOW_MUSICXML2LY)"

_TIMEOUT_S = 120


def find_lilypond() -> str | None:
    """Path to ``lilypond``, or None.

    ``FIELDSHOW_ENGRAVER`` and ``FIELDSHOW_LILYPOND`` are used as given.
    A set variable that does not point at a file is missing; lookup does not
    fall through to ``PATH``.
    """
    for var in ("FIELDSHOW_ENGRAVER", "FIELDSHOW_LILYPOND"):
        if var in os.environ:
            return _existing_file(os.environ[var])
    return shutil.which("lilypond")


def find_musicxml2ly() -> str | None:
    if "FIELDSHOW_MUSICXML2LY" in os.environ:
        return _existing_file(os.environ["FIELDSHOW_MUSICXML2LY"])
    return shutil.which("musicxml2ly")


def engrave_parts(show: dict, output: str | Path) -> dict:
    """Write ``parts/<section>.pdf`` next to ``output`` and record the paths.

    Missing tools or a failing part leave that path null and set
    ``engrave_error``. The show JSON is still the caller's to save.
    """
    show["part_pdfs"] = {section: None for section in SECTION_ORDER}
    lilypond = find_lilypond()
    converter = find_musicxml2ly()
    if not lilypond or not converter:
        message = MISSING_ENGRAVER if not lilypond else MISSING_CONVERTER
        show["engrave_error"] = message
        print(message, file=sys.stderr)
        return show

    show["engrave_error"] = None
    base = Path(output).parent
    errors: list[str] = []
    for section in SECTION_ORDER:
        dest = base / "parts" / f"{section}.pdf"
        try:
            _engrave_one(show, section, dest, lilypond, converter)
        except (OSError, subprocess.TimeoutExpired, RuntimeError) as exc:
            if dest.is_file():
                dest.unlink()
            detail = f"{section}: {exc}"
            errors.append(detail)
            print(f"PDF parts unavailable: {detail}", file=sys.stderr)
            continue
        show["part_pdfs"][section] = f"parts/{section}.pdf"
    if errors:
        show["engrave_error"] = "PDF parts unavailable: " + "; ".join(errors)
    return show


def _engrave_one(show: dict, section: str, dest: Path, lilypond: str, converter: str) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="fieldshow-engrave-") as tmp:
        work = Path(tmp)
        xml_path = work / f"{section}.musicxml"
        ly_path = work / f"{section}.ly"
        export_musicxml(show, xml_path, section=section)
        converted = subprocess.run(
            [converter, "-o", str(ly_path), str(xml_path)],
            capture_output=True,
            text=True,
            timeout=_TIMEOUT_S,
            check=False,
        )
        if converted.returncode != 0 or not ly_path.is_file():
            raise RuntimeError(
                f"musicxml2ly exited {converted.returncode}: {_tail(converted.stderr or converted.stdout)}"
            )
        prefix = work / section
        rendered = subprocess.run(
            [lilypond, "--pdf", "-o", str(prefix), str(ly_path)],
            capture_output=True,
            text=True,
            timeout=_TIMEOUT_S,
            check=False,
        )
        pdf = prefix.with_suffix(".pdf")
        if rendered.returncode != 0 or not pdf.is_file():
            raise RuntimeError(
                f"lilypond exited {rendered.returncode}: {_tail(rendered.stderr or rendered.stdout)}"
            )
        dest.write_bytes(pdf.read_bytes())


def _existing_file(value: str) -> str | None:
    path = Path(value)
    if path.is_file():
        return str(path)
    return None


def _tail(text: str, limit: int = 300) -> str:
    compact = " ".join(text.split())
    if not compact:
        return "no output"
    return compact[-limit:]
