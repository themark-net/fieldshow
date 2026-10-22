"""Engrave one PDF per part. LilyPond is the engraver (ADR 0004)."""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
import tempfile
from pathlib import Path

from fieldshow.model import SECTION_ORDER
from fieldshow.music.io import export_musicxml

# Printed when the binary is missing. build still exits 0.
MISSING_ENGRAVER = "PDF parts unavailable: LilyPond not found (set FIELDSHOW_ENGRAVER)"
MISSING_CONVERTER = "PDF parts unavailable: musicxml2ly not found (set FIELDSHOW_MUSICXML2LY)"

# Each musicxml2ly and lilypond call. A hung Ghostscript is in that process group.
_DEFAULT_TIMEOUT_S = 120


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
    ``engrave_error``. Per-part page text is the short ``part_errors`` value.
    The show JSON is still the caller's to save. Existing part PDFs are removed
    first so a failed or skipped engrave cannot leave a stale file on disk.
    """
    show["part_pdfs"] = {section: None for section in SECTION_ORDER}
    show["part_errors"] = {}
    base = Path(output).parent
    _clear_part_pdfs(base)
    lilypond = find_lilypond()
    converter = find_musicxml2ly()
    if not lilypond or not converter:
        message = MISSING_ENGRAVER if not lilypond else MISSING_CONVERTER
        show["engrave_error"] = message
        print(message, file=sys.stderr)
        return show

    show["engrave_error"] = None
    errors: list[str] = []
    for section in SECTION_ORDER:
        dest = base / "parts" / f"{section}.pdf"
        try:
            _engrave_one(show, section, dest, lilypond, converter)
        except (OSError, subprocess.TimeoutExpired, RuntimeError) as exc:
            short = _short_reason(exc)
            show["part_errors"][section] = short
            detail = f"{section}: {exc}"
            errors.append(detail)
            print(f"PDF parts unavailable: {detail}", file=sys.stderr)
            continue
        show["part_pdfs"][section] = f"parts/{section}.pdf"
    if errors:
        show["engrave_error"] = "PDF parts unavailable: " + "; ".join(errors)
    return show


def _clear_part_pdfs(base: Path) -> None:
    parts = base / "parts"
    for section in SECTION_ORDER:
        stale = parts / f"{section}.pdf"
        if stale.is_symlink() or stale.is_file():
            stale.unlink()


def _engrave_one(show: dict, section: str, dest: Path, lilypond: str, converter: str) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="fieldshow-engrave-") as tmp:
        work = Path(tmp)
        xml_path = work / f"{section}.musicxml"
        ly_path = work / f"{section}.ly"
        export_musicxml(show, xml_path, section=section)
        converted = _run([converter, "-o", str(ly_path), str(xml_path)])
        if converted.returncode != 0 or not ly_path.is_file():
            raise RuntimeError(
                f"musicxml2ly exited {converted.returncode}: {_tail(converted.stderr or converted.stdout)}"
            )
        prefix = work / section
        rendered = _run([lilypond, "--pdf", "-o", str(prefix), str(ly_path)])
        pdf = prefix.with_suffix(".pdf")
        if rendered.returncode != 0 or not pdf.is_file():
            raise RuntimeError(
                f"lilypond exited {rendered.returncode}: {_tail(rendered.stderr or rendered.stdout)}"
            )
        dest.write_bytes(pdf.read_bytes())


def _run(argv: list[str]) -> subprocess.CompletedProcess[str]:
    """Run ``argv`` as a new session so a timeout can kill grandchildren too.

    Real LilyPond spawns Ghostscript. ``subprocess.run(..., timeout=)`` would
    leave that child behind. ``FIELDSHOW_ENGRAVE_TIMEOUT`` is seconds (default 120).
    """
    timeout = _timeout_s()
    proc = subprocess.Popen(
        argv,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        proc.communicate()
        raise
    return subprocess.CompletedProcess(argv, proc.returncode, stdout, stderr)


def _timeout_s() -> float:
    raw = os.environ.get("FIELDSHOW_ENGRAVE_TIMEOUT", "").strip()
    if not raw:
        return float(_DEFAULT_TIMEOUT_S)
    return float(raw)


def _existing_file(value: str) -> str | None:
    path = Path(value)
    if path.is_file():
        return str(path)
    return None


def _short_reason(exc: BaseException) -> str:
    """Page text. The stderr tail stays on stderr and in ``engrave_error``."""
    if isinstance(exc, subprocess.TimeoutExpired):
        return "timed out"
    text = str(exc).strip()
    head, sep, _rest = text.partition(": ")
    if sep and head:
        return head
    return text[:80] or "failed"


def _tail(text: str, limit: int = 300) -> str:
    compact = " ".join(text.split())
    if not compact:
        return "no output"
    return compact[-limit:]
