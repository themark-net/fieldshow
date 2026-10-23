"""Integrated server: one show, music, drill, and design on one page."""

import gc
import os
import signal
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest
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


def test_lifespan_shutdown_removes_the_assets_dir():
    """The server's own shutdown removes the dir; no GC and no interpreter exit needed."""
    app = create_app()
    assets = Path(app.state.assets)
    with TestClient(app) as client:
        assert client.get("/api/health").status_code == 200
        assert assets.is_dir()
    assert not assets.exists()
    with TestClient(app) as client:
        assert client.get("/api/health").status_code == 200
        assert assets.is_dir(), "a second lifespan must get its dir back"
    assert not assets.exists()


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.mark.parametrize("sig", [signal.SIGTERM, signal.SIGINT], ids=["SIGTERM", "SIGINT"])
def test_stopped_server_leaves_no_assets_dir(tmp_path: Path, sig: int):
    """``kill``, systemd and ``docker stop`` send SIGTERM; uvicorn re-raises it, so no finalizer runs."""
    env = os.environ.copy()
    env["TMPDIR"] = str(tmp_path)
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
    port = _free_port()
    proc = subprocess.Popen(
        [sys.executable, "-m", "fieldshow", "serve", "--host", "127.0.0.1", "--port", str(port)],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    try:
        deadline = time.monotonic() + 30
        healthy = False
        while time.monotonic() < deadline and proc.poll() is None:
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1) as reply:
                    healthy = reply.status == 200
            except OSError:
                time.sleep(0.1)
                continue
            break
        assert healthy, proc.stdout.read().decode(errors="replace") if proc.poll() is not None else "no health"
        assert len(list(tmp_path.glob("fieldshow-*"))) == 1
        proc.send_signal(sig)
        out, _ = proc.communicate(timeout=30)
        assert list(tmp_path.glob("fieldshow-*")) == [], (proc.returncode, out.decode(errors="replace"))
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(10)
