"""Integrated server: one show, music, drill, and design on one page."""

import gc
import os
import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from fieldshow.model import demo_show
from fieldshow.web.app import create_app

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 16


def test_page_and_frame_share_one_show(tmp_path: Path):
    client = TestClient(create_app(demo_show()))
    page = client.get("/")
    assert page.status_code == 200
    body = page.text
    assert "Gate Fanfare" in body
    assert 'type="range"' in body
    health = client.get("/api/health")
    assert health.json()["ok"] is True
    show = client.get("/api/show").json()
    assert show["parts"]["trumpet"][0] == "C5"
    assert len(show["performers"]) == 12
    assert show["design"]["palette"][0] == "#e8a838"
    frame = client.get("/api/frame", params={"beat": 4}).json()
    assert len(frame["positions"]) == 12
    assert frame["beat"] == 4
    playback = client.get("/api/playback").json()
    assert playback[0]["part"] == "flute"
    updated = client.post("/api/intent", json={"title": "Revised Gate", "tempo": 120})
    assert updated.status_code == 200
    assert client.get("/api/show").json()["title"] == "Revised Gate"
    image = client.post("/api/image", files={"image": ("field.png", PNG, "image/png")})
    assert image.status_code == 200
    stored = client.get("/api/show").json()["field_image"]
    assert stored
    picture = client.get("/api/field-image")
    assert picture.status_code == 200
    assert picture.content.startswith(b"\x89PNG")


def _drop_fastapi_callable_cache() -> None:
    """FastAPI's callable-classification cache holds the route functions.

    Those functions close over the app, so ``gc.collect()`` cannot collect it
    until the cache drops them.
    """
    import fastapi.dependencies.models as models

    for name in dir(models):
        clear = getattr(getattr(models, name), "cache_clear", None)
        if clear is not None:
            clear()


def test_assets_dir_is_removed_when_the_app_is_collected():
    app = create_app()
    assets = Path(app.state.assets)
    assert assets.is_dir()
    assert assets.name.startswith("fieldshow-")
    _drop_fastapi_callable_cache()
    del app
    gc.collect()
    assert not assets.exists()


def test_process_exit_removes_the_assets_dir(tmp_path: Path):
    env = os.environ.copy()
    env["TMPDIR"] = str(tmp_path)
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
    run = subprocess.run(
        [sys.executable, "-c", "from fieldshow.web.app import create_app; create_app()"],
        env=env,
        capture_output=True,
        text=True,
    )
    assert run.returncode == 0, run.stderr
    assert list(tmp_path.glob("fieldshow-*")) == []
