"""One page for the score, the field, and the design notes."""

from __future__ import annotations

import contextlib
import copy
import os
import shutil
import stat
import tempfile
import weakref
from html import escape
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, Response

from fieldshow.drill.chart import chart, interpolate
from fieldshow.drill.image import import_image
from fieldshow.model import (
    FIELD_IMAGE_RULE,
    FIELD_IMAGE_SUFFIXES,
    SECTION_ORDER,
    apply_intent,
    demo_show,
    field_image_ok,
    load_show,
)
from fieldshow.music.arrange import arrange, playback
from fieldshow.music.io import PART_NAMES

_PAGE = Path(__file__).with_name("static") / "index.html"

# Stored suffix comes from the bytes, and it has to be one of FIELD_IMAGE_SUFFIXES.
# JPEG is .jpg. FIELD_IMAGE_SUFFIXES also lists .jpeg; the stored name does not.
_IMAGE_MAGIC = (
    (b"\x89PNG\r\n\x1a\n", ".png"),
    (b"\xff\xd8\xff", ".jpg"),
    (b"GIF87a", ".gif"),
    (b"GIF89a", ".gif"),
)


def _sniffed_image_suffix(data: bytes) -> str | None:
    """Return the stored suffix for image magic, or None when the bytes are not an image."""
    for magic, suffix in _IMAGE_MAGIC:
        if data.startswith(magic) and suffix in FIELD_IMAGE_SUFFIXES:
            return suffix
    if (
        len(data) >= 12
        and data.startswith(b"RIFF")
        and data[8:12] == b"WEBP"
        and ".webp" in FIELD_IMAGE_SUFFIXES
    ):
        return ".webp"
    return None


class _AssetsDir:
    """This app's private upload dir.

    Made by ``mkdtemp`` (mode 0700, this euid) and remembered by device and
    inode. It is used, and removed, only while ``lstat`` still shows that same
    real dir with that owner and mode. A name freed by an earlier cleanup is
    never taken back: in a shared TMPDIR whatever sits there now may belong to
    someone else, so the next use gets a fresh ``mkdtemp``.
    """

    def __init__(self) -> None:
        self.path: Path | None = None
        self._ident: tuple[int, int] | None = None

    def current(self) -> Path | None:
        """The dir if it is still the one we made, else None."""
        if self.path is None:
            return None
        try:
            st = os.lstat(self.path)
        except OSError:
            return None
        if (
            stat.S_ISDIR(st.st_mode)
            and (st.st_dev, st.st_ino) == self._ident
            and st.st_uid == os.geteuid()
            and stat.S_IMODE(st.st_mode) == 0o700
        ):
            return self.path
        return None

    def ensure(self) -> Path:
        path = self.current()
        if path is None:
            path = Path(tempfile.mkdtemp(prefix="fieldshow-"))
            st = os.lstat(path)
            self.path, self._ident = path, (st.st_dev, st.st_ino)
        return path

    def remove(self) -> None:
        """Remove the dir only if it is still ours; then forget it either way."""
        path = self.current()
        if path is not None:
            shutil.rmtree(path, ignore_errors=True)
        self.path = self._ident = None


def _rebuild(show: dict) -> dict:
    built = arrange(show)
    return chart(built)


def create_app(show: dict | None = None, show_path: str | Path | None = None) -> FastAPI:
    if show is None:
        show = load_show(show_path) if show_path else demo_show()
    else:
        show = copy.deepcopy(show)

    assets = _AssetsDir()

    @contextlib.asynccontextmanager
    async def lifespan(_app: FastAPI):
        # The dir is made here, not in create_app: uvicorn has its signal
        # handlers in place by now, so a SIGTERM during startup still reaches
        # the shutdown below. The shutdown is the one cleanup that runs on
        # SIGTERM: uvicorn shuts down, then re-raises the signal, so neither
        # the finalizer below nor atexit gets a chance.
        assets.remove()
        _app.state.assets = assets.ensure()
        try:
            yield
        finally:
            assets.remove()
            _app.state.assets = None

    app = FastAPI(title="Fieldshow", lifespan=lifespan)
    app.state.assets_dir = assets
    # The path of the dir in use, for tests and callers; None until an upload
    # or a lifespan makes one.
    app.state.assets = None
    # Backup for an app that never ran a lifespan (tests, embedding), or an
    # interpreter that exits normally. remove() checks the dir is still ours.
    weakref.finalize(app, assets.remove)
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
        try:
            merged = apply_intent(app.state.show, body)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        if (
            "field_image" in body
            and merged.get("field_image") is not None
            and _field_image_file(app, merged["field_image"]) is None
        ):
            raise HTTPException(status_code=422, detail=FIELD_IMAGE_RULE)
        if any(key in body for key in ("title", "author", "key", "meter", "tempo", "melody", "chords")):
            merged["part_pdfs"] = {section: None for section in SECTION_ORDER}
            merged["engrave_error"] = "parts changed; run fieldshow build to refresh PDFs"
        app.state.show = _rebuild(merged)
        return {"title": app.state.show["title"]}

    @app.post("/api/image")
    async def upload_image(image: UploadFile = File(...)) -> dict:
        # A present client suffix has to be an image suffix before any scratch file exists.
        # The stored name still comes from the bytes, not from this suffix.
        assets = app.state.assets_dir.ensure()
        app.state.assets = assets
        client_suffix = Path(image.filename or "").suffix
        if client_suffix and client_suffix.lower() not in FIELD_IMAGE_SUFFIXES:
            raise HTTPException(
                status_code=415,
                detail="field image must be png, jpg, webp, or gif",
            )
        data = await image.read()
        suffix = _sniffed_image_suffix(data)
        if suffix is None:
            raise HTTPException(
                status_code=415,
                detail="field image must be png, jpg, webp, or gif",
            )
        images = assets / "images"
        if images.is_symlink() or (images.exists() and not images.is_dir()):
            # Never write through a link; this dir is 0700 and ours, so this is a fault.
            raise HTTPException(status_code=500, detail="upload images dir is not a real dir")
        incoming = assets / f"upload{suffix}"
        try:
            incoming.write_bytes(data)
            app.state.show = import_image(app.state.show, incoming, assets)
        except ValueError as exc:
            raise HTTPException(status_code=415, detail=str(exc)) from exc
        finally:
            incoming.unlink(missing_ok=True)
        return {"field_image": app.state.show["field_image"]}

    @app.get("/api/field-image")
    def field_image() -> Response:
        path = _field_image_file(app, app.state.show.get("field_image"))
        if path is None:
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


def _field_image_file(app: FastAPI, value: object) -> Path | None:
    """``images/<name>`` under this server's upload dir or the show dir, else None.

    The stored string is checked again here, because a show JSON on disk is not
    an intent. Each root's ``images/`` must resolve inside that root, and the file
    must resolve inside that ``images/``, be a regular file, and open for reading,
    so an unreadable file is refused here instead of failing mid-response.
    """
    if value is None or not field_image_ok(value):
        return None
    assets = app.state.assets_dir.current()
    roots = [assets] if assets is not None else []
    if app.state.show_dir is not None:
        roots.append(app.state.show_dir)
    for root in roots:
        try:
            base = Path(root).resolve()
            images = (Path(root) / "images").resolve()
            if not images.is_relative_to(base):
                continue
            path = (Path(root) / str(value)).resolve()
            if path.is_relative_to(images) and path.is_file():
                with path.open("rb"):
                    pass
                return path
        except (ValueError, OSError, RuntimeError):
            continue
    return None


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
