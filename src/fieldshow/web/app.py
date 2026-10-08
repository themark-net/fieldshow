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
from fieldshow.model import apply_intent, demo_show, load_show
from fieldshow.music.arrange import arrange, playback

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

    @app.get("/")
    def index() -> HTMLResponse:
        title = escape(app.state.show["title"])
        html = _PAGE.read_text().replace("{{title}}", title)
        return HTMLResponse(html)

    return app
