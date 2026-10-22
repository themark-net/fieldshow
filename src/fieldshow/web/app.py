"""One page for the score, the field, and the design notes."""

from __future__ import annotations

import copy
import tempfile
from html import escape
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, Response

from fieldshow.drill.chart import chart, interpolate
from fieldshow.drill.image import import_image
from fieldshow.model import SECTION_ORDER, apply_intent, demo_show, load_show
from fieldshow.music.arrange import arrange, playback
from fieldshow.music.io import PART_NAMES

_PAGE = Path(__file__).with_name("static") / "index.html"


def _rebuild(show: dict) -> dict:
    built = arrange(show)
    return chart(built)


def create_app(show: dict | None = None, show_path: str | Path | None = None) -> FastAPI:
    if show is None:
        show = load_show(show_path) if show_path else demo_show()
    else:
        show = copy.deepcopy(show)

    app = FastAPI(title="Fieldshow")
    app.state.assets = Path(tempfile.mkdtemp(prefix="fieldshow-"))
    app.state.show_dir = Path(show_path).resolve().parent if show_path else None
    app.state.show = _rebuild(show)

    @app.get("/api/health")
    def health() -> dict:
        return {"ok": True}

    @app.get("/api/show")
    def current() -> dict:
        return app.state.show

    @app.get("/api/frame")
    def frame(beat: float = 0) -> dict:
        current_show = app.state.show
        return {
            "beat": beat,
            "tempo": current_show["tempo"],
            "positions": interpolate(current_show, beat),
        }

    @app.get("/api/playback")
    def play() -> list:
        return playback(app.state.show)

    @app.post("/api/intent")
    def intent(body: dict) -> dict:
        merged = apply_intent(app.state.show, body)
        if any(key in body for key in ("title", "author", "key", "meter", "tempo", "melody", "chords")):
            merged["part_pdfs"] = {section: None for section in SECTION_ORDER}
            merged["engrave_error"] = "parts changed; run fieldshow build to refresh PDFs"
        app.state.show = _rebuild(merged)
        return {"title": app.state.show["title"]}

    @app.post("/api/image")
    async def upload_image(image: UploadFile = File(...)) -> dict:
        suffix = Path(image.filename or "field.png").suffix or ".png"
        incoming = app.state.assets / f"upload{suffix}"
        incoming.write_bytes(await image.read())
        app.state.show = import_image(app.state.show, incoming, app.state.assets)
        return {"field_image": app.state.show["field_image"]}

    @app.get("/api/field-image")
    def field_image() -> Response:
        path = app.state.show.get("field_image")
        if not path or not Path(path).is_file():
            raise HTTPException(status_code=404, detail="no field image")
        return FileResponse(path)

    @app.get("/api/part-pdf/{section}")
    def part_pdf(section: str) -> Response:
        path = _part_pdf_file(app, section)
        if path is None:
            raise HTTPException(status_code=404, detail="part PDF unavailable")
        return FileResponse(path, media_type="application/pdf", filename=f"{section}.pdf")

    @app.get("/")
    def index() -> HTMLResponse:
        title = escape(app.state.show["title"])
        html = (
            _PAGE.read_text()
            .replace("{{title}}", title)
            .replace("{{part_pdfs}}", _paper_html(app.state.show))
        )
        return HTMLResponse(html)

    return app


def _paper_html(show: dict) -> str:
    """Server-rendered so a client that does not run the script still sees the state.

    A missing engraver is one line plus a plain "unavailable" on each row, so the
    sentence is not "unavailable: PDF parts unavailable...". A failed part shows
    only its short ``part_errors`` reason. The stderr tail stays off the page.
    """
    pdfs = show.get("part_pdfs") or {}
    part_errors = show.get("part_errors") or {}
    items: list[str] = []
    if not part_errors and show.get("engrave_error"):
        items.append(f'<li class="engrave-note">{escape(show["engrave_error"])}</li>')
    for section in SECTION_ORDER:
        label = escape(PART_NAMES[section])
        rel = pdfs.get(section)
        if rel:
            items.append(
                f'<li>{label} <a href="/api/part-pdf/{escape(section)}">PDF</a></li>'
            )
            continue
        short = part_errors.get(section)
        if short:
            items.append(
                f'<li>{label} <span class="unavailable">unavailable: {escape(short)}</span></li>'
            )
        elif show.get("engrave_error"):
            items.append(f'<li>{label} <span class="unavailable">unavailable</span></li>')
        else:
            items.append(
                f'<li>{label} <span class="unavailable">unavailable: not engraved</span></li>'
            )
    return "\n".join(items)


def _part_pdf_file(app: FastAPI, section: str) -> Path | None:
    """Only ``<show_dir>/parts/<section>.pdf`` for a known section.

    ``part_pdfs`` is a marker, not a path. Null and any other string 404.
    The opened path is computed, resolved, and kept inside ``parts/``, and
    ``parts/`` itself must resolve inside the show directory.
    """
    if section not in SECTION_ORDER:
        return None
    show_dir = app.state.show_dir
    entry = (app.state.show.get("part_pdfs") or {}).get(section)
    if entry != f"parts/{section}.pdf" or show_dir is None:
        return None
    try:
        show_root = Path(show_dir).resolve()
        parts_dir = (Path(show_dir) / "parts").resolve()
        if not parts_dir.is_relative_to(show_root):
            return None
        path = (parts_dir / f"{section}.pdf").resolve()
        if not path.is_relative_to(parts_dir) or not path.is_file():
            return None
        return path
    except (ValueError, OSError, RuntimeError):
        # RuntimeError: Python 3.12 Path.resolve() on a symlink loop.
        return None
