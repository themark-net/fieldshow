"""Integrated server: one show, music, drill, and design on one page."""

import gc
import os
import signal
import shutil
import socket
import stat
import subprocess
import sys
import tempfile
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
    client = TestClient(app)
    assert client.post("/api/image", files={"image": ("f.png", PNG, "image/png")}).status_code == 200
    assets = Path(app.state.assets)
    assert assets.is_dir()
    assert assets.name.startswith("fieldshow-")
    _drop_fastapi_callable_cache()
    del client, app
    gc.collect()
    assert not assets.exists()


def test_process_exit_removes_the_assets_dir(tmp_path: Path):
    env = os.environ.copy()
    env["TMPDIR"] = str(tmp_path)
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
    run = subprocess.run(
        [
            sys.executable,
            "-c",
            "from fastapi.testclient import TestClient\n"
            "from fieldshow.web.app import create_app\n"
            "client = TestClient(create_app())\n"
            "png = b'\\x89PNG\\r\\n\\x1a\\n' + b'0' * 16\n"
            "reply = client.post('/api/image', files={'image': ('f.png', png, 'image/png')})\n"
            "assert reply.status_code == 200, reply.text\n"
            "print(client.app.state.assets)\n",
        ],
        env=env,
        capture_output=True,
        text=True,
    )
    assert run.returncode == 0, run.stderr
    assert run.stdout.strip().startswith(str(tmp_path / "fieldshow-"))
    assert list(tmp_path.glob("fieldshow-*")) == []


def _own_private_dir(path: Path) -> bool:
    st = path.lstat()
    return stat.S_ISDIR(st.st_mode) and st.st_uid == os.geteuid() and stat.S_IMODE(st.st_mode) == 0o700


def test_lifespan_shutdown_removes_the_assets_dir():
    """The server's own shutdown removes the dir; no GC and no interpreter exit needed.

    Each lifespan works in a private dir it made itself, and leaves nothing.
    """
    app = create_app()
    for _ in range(2):
        with TestClient(app) as client:
            assert client.post("/api/image", files={"image": ("f.png", PNG, "image/png")}).status_code == 200
            assets = Path(app.state.assets)
            assert _own_private_dir(assets)
        assert not assets.exists()


def _plant(path: Path, victim: Path, link_images: bool) -> None:
    """What another uid can do with a freed ``fieldshow-*`` name in a shared 1777 TMPDIR."""
    path.mkdir()
    path.chmod(0o777)
    (path / "theirs.txt").write_text("theirs")
    if link_images:
        (path / "images").symlink_to(victim, target_is_directory=True)


@pytest.mark.parametrize("link_images", [False, True], ids=["foreign-dir", "images-symlink"])
def test_second_lifespan_does_not_take_over_a_dir_planted_at_the_freed_name(
    tmp_path: Path, monkeypatch, link_images: bool
):
    """Reviewer M1-r4: never use, write through, or empty a dir this app did not make."""
    shared = tmp_path / "shared"
    shared.mkdir()
    victim = tmp_path / "victim"
    victim.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(shared))
    app = create_app()
    with TestClient(app) as client:
        assert client.get("/api/health").status_code == 200
        first = Path(app.state.assets)
    assert not first.exists()
    _plant(first, victim, link_images)
    with TestClient(app) as client:
        reply = client.post("/api/image", files={"image": ("f.png", PNG, "image/png")})
        assert reply.status_code == 200, reply.text
        used = Path(app.state.assets)
        assert used != first
        assert _own_private_dir(used)
        assert (used / "images" / "field.png").is_file()
    assert list(victim.iterdir()) == []
    assert (first / "theirs.txt").read_text() == "theirs"
    assert stat.S_IMODE(first.lstat().st_mode) == 0o777
    assert not used.exists()


def test_upload_never_writes_through_an_images_link(tmp_path: Path):
    """``images/`` must be a real dir; a symlink there is refused, nothing is written through it."""
    victim = tmp_path / "victim"
    victim.mkdir()
    client = TestClient(create_app(), raise_server_exceptions=False)
    assert client.post("/api/image", files={"image": ("f.png", PNG, "image/png")}).status_code == 200
    images = Path(client.app.state.assets) / "images"
    shutil.rmtree(images)
    images.symlink_to(victim, target_is_directory=True)
    reply = client.post("/api/image", files={"image": ("f.png", PNG, "image/png")})
    assert reply.status_code == 500, reply.text
    assert list(victim.iterdir()) == []
    assert list(Path(client.app.state.assets).glob("upload*")) == []


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


def test_sigterm_during_startup_leaves_no_assets_dir(tmp_path: Path):
    """SIGTERM the moment the dir appears, ten times: before r5 the dir was made before
    uvicorn caught signals, so this killed the process outright and left it behind."""
    src = str(Path(__file__).resolve().parents[1] / "src")
    leaks = []
    for attempt in range(10):
        private = tmp_path / f"run{attempt}"
        private.mkdir()
        env = os.environ.copy()
        env["TMPDIR"] = str(private)
        env["PYTHONPATH"] = src
        proc = subprocess.Popen(
            [sys.executable, "-m", "fieldshow", "serve", "--host", "127.0.0.1", "--port", str(_free_port())],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        try:
            deadline = time.monotonic() + 30
            while not list(private.glob("fieldshow-*")) and proc.poll() is None and time.monotonic() < deadline:
                time.sleep(0.001)
            assert proc.poll() is None, proc.stdout.read().decode(errors="replace")
            assert list(private.glob("fieldshow-*")), "the server never made its dir"
            proc.send_signal(signal.SIGTERM)
            out, _ = proc.communicate(timeout=30)
            left = list(private.glob("fieldshow-*"))
            if left:
                leaks.append((attempt, proc.returncode, [p.name for p in left]))
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait(10)
    assert leaks == []
