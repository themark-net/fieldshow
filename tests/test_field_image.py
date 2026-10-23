"""field_image is only ever a file under images/ in the show dir or the upload dir (#3)."""

from __future__ import annotations

import contextlib
import json
import os
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from fieldshow.model import apply_intent, demo_show, load_show
from fieldshow.web.app import create_app

PNG = b"\x89PNG\r\n\x1a\n" + b"field-ok" * 4
SECRET = b"TOP-SECRET-OUTSIDE-SHOWDIR\n"


def _show_dir(tmp_path: Path, field_image: str | None) -> tuple[Path, Path]:
    """A show dir with a real images/field.png and a secret file outside it."""
    show_dir = tmp_path / "show"
    (show_dir / "images").mkdir(parents=True)
    (show_dir / "images" / "field.png").write_bytes(PNG)
    secret = tmp_path / "secret.png"
    secret.write_bytes(SECRET)
    (show_dir / "images" / "out.png").symlink_to(secret)
    show = demo_show()
    show["field_image"] = field_image
    path = show_dir / "show.json"
    path.write_text(json.dumps(show))
    return path, secret


def _client(path: Path) -> TestClient:
    return TestClient(create_app(load_show(path), show_path=path), raise_server_exceptions=False)


NAME64 = "n" * 64

# One table for every refused value. _plant() puts a real file (or a directory,
# or an unreadable file) at each value that is a creatable path inside the show
# dir, so a refusal is the rule's doing, not a missing file.
BAD = [
    # traversal and absolute
    "../secret.png",
    "images/../../secret.png",
    "%2e%2e%2fsecret.png",
    "images/%2e%2e%2f%2e%2e%2fsecret.png",
    "/etc/passwd",
    "SECRET_ABS",
    "ABS_LEGIT",
    "images/out.png",
    "images/field.png\x00",
    "show.json",
    "images/missing.png",
    # non-canonical spellings of the real image
    "images/./field.png",
    "images/x/../field.png",
    "images//field.png",
    # name and extension rule (B1, T2), each file present on disk
    "images/x.png\n",
    "images/x.txt.png",
    "images/x.png.txt",
    "images/a.b.png",
    "images/" + "n" * 65 + ".png",
    "images/.png",
    "images/\u212a.png",
    "image\u017f/x.png",
    "images/x.svg",
    "images/x.json",
    "images/field.txt",
    "images/sub/x.png",
    # not a readable regular file (S1, T1, T2)
    "images/dir.png",
    "images/unread.png",
]
GOOD = ["images/" + NAME64 + ".png", "images/x.PNG"]


def _value(bad: str, secret: Path, show_dir: Path | None = None) -> str:
    if bad == "SECRET_ABS":
        return str(secret)
    if bad == "ABS_LEGIT":
        return str((show_dir or secret.parent / "show") / "images" / "field.png")
    return bad


def _plant(show_dir: Path, value: str) -> None:
    """Create what a value names, when it is a plain relative path in the show dir."""
    if value.startswith("/") or ".." in value or "%" in value or "\x00" in value:
        return
    if value in ("show.json", "images/missing.png"):
        return
    target = show_dir / value
    if value == "images/dir.png":
        target.mkdir(parents=True)
        return
    if target.exists() or target.is_symlink():
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(PNG + b"-planted")
    if value == "images/unread.png":
        target.chmod(0)


_CHILD_WAIT_SECONDS = 60


@contextlib.contextmanager
def _reachable_by_others(tmp_path: Path):
    """Let another uid reach ``tmp_path`` while the block runs.

    ``tmp_path`` itself is opened to 0755, like the dirs inside it. Each ancestor
    up to ``/`` that lacks ``o+x`` gets search only (no read, no write), because
    pytest makes ``/tmp/pytest-of-<user>`` and its basetemp 0700. Every ancestor
    mode is put back when the block ends, so nothing above the test stays wider.
    """
    tmp_path.chmod(0o755)
    changed: list[tuple[Path, int]] = []
    try:
        for parent in tmp_path.parents:
            mode = stat.S_IMODE(parent.stat().st_mode)
            if not mode & stat.S_IXOTH:
                parent.chmod(mode | stat.S_IXOTH)
                changed.append((parent, mode))
        yield
    finally:
        for parent, mode in reversed(changed):
            parent.chmod(mode)


def _wait_child(pid: int, timeout: float) -> int:
    """Wait until ``pid`` exits. After ``timeout`` seconds, SIGKILL it and raise."""
    deadline = time.monotonic() + timeout
    while True:
        done, status = os.waitpid(pid, os.WNOHANG)
        if done:
            return os.waitstatus_to_exitcode(status)
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        time.sleep(min(0.05, remaining))
    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    _done, status = os.waitpid(pid, 0)
    code = os.waitstatus_to_exitcode(status)
    raise AssertionError(
        f"child {pid} was still running after {timeout:.0f}s; killed it (exit {code})"
    )


def _unprivileged(tmp_path: Path, check) -> None:
    """Run ``check`` as a non-root uid, so file permissions apply even in a root container."""
    if os.geteuid() != 0:
        check()
        return
    for path in tmp_path.rglob("*"):
        if path.is_dir() and not path.is_symlink() and path.name != "dir.png":
            path.chmod(0o755)
    with _reachable_by_others(tmp_path):
        _run_as_nobody(check)


def _nobody_temp_dirs() -> set[Path]:
    return {
        path
        for path in Path(tempfile.gettempdir()).glob("fieldshow-*")
        if path.is_dir() and not path.is_symlink() and path.lstat().st_uid == 65534
    }


def _run_as_nobody(check) -> None:
    """Fork, drop to uid 65534, run ``check``.

    The child leaves with ``os._exit``, so the app finalizer that removes each
    ``fieldshow-*`` upload dir never runs there. The parent removes the dirs
    that child created once it has been reaped.
    """
    before = _nobody_temp_dirs()
    try:
        _fork_as_nobody(check)
    finally:
        for path in _nobody_temp_dirs() - before:
            shutil.rmtree(path, ignore_errors=True)


def _fork_as_nobody(check) -> None:
    pid = os.fork()
    if pid == 0:
        code = 1
        try:
            os.setgroups([])
            os.setgid(65534)
            os.setuid(65534)
            check()
            code = 0
        except BaseException:
            import traceback

            traceback.print_exc()
        finally:
            os._exit(code)
    status = _wait_child(pid, _CHILD_WAIT_SECONDS)
    assert status == 0, "check failed as uid 65534"


def _mode(path: Path) -> int:
    return path.stat().st_mode & 0o777


def test_reachable_by_others_adds_only_search_and_restores(tmp_path: Path):
    """uid 65534 needs ``x`` on every ancestor, ``/tmp/pytest-of-<user>`` included (0700 by default).

    Only ``o+x`` is added, only where it is missing, and every mode is put back.
    """
    above = tmp_path / "above"
    mid = above / "mid"
    leaf = mid / "leaf"
    leaf.mkdir(parents=True)
    above.chmod(0o700)
    mid.chmod(0o750)
    ancestors = list(leaf.parents)
    snapshot = {parent: _mode(parent) for parent in ancestors}
    try:
        with _reachable_by_others(leaf):
            missing = [str(parent) for parent in ancestors if not _mode(parent) & 0o001]
            assert missing == [], f"no o+x on {missing}"
            assert _mode(above) == 0o701, oct(_mode(above))
            assert _mode(mid) == 0o751, oct(_mode(mid))
            for parent in ancestors:
                assert _mode(parent) & ~0o001 == snapshot[parent] & ~0o001, parent
        after = {parent: _mode(parent) for parent in ancestors}
        assert after == snapshot
    finally:
        for parent in reversed(ancestors):
            if _mode(parent) != snapshot[parent]:
                parent.chmod(snapshot[parent])


@pytest.mark.skipif(os.geteuid() != 0, reason="the uid 65534 child only runs as root")
def test_unprivileged_child_leaves_no_upload_dirs(tmp_path: Path):
    """As root the child builds apps as uid 65534 and leaves via os._exit, so the parent cleans up."""
    path, _ = _show_dir(tmp_path, "images/field.png")
    before = _nobody_temp_dirs()

    def check() -> None:
        assert _client(path).get("/api/field-image").status_code == 200

    _unprivileged(tmp_path, check)
    assert _nobody_temp_dirs() - before == set()

def test_wait_child_kills_a_hung_child_within_the_timeout():
    """A child that sleeps forever is killed, and the helper raises, inside the timeout."""
    pid = os.fork()
    if pid == 0:
        time.sleep(3600)
        os._exit(0)
    box: dict = {}

    def run() -> None:
        try:
            box["status"] = _wait_child(pid, 1)
        except BaseException as exc:
            box["error"] = exc

    worker = threading.Thread(target=run, daemon=True)
    worker.start()
    try:
        worker.join(10)
        if worker.is_alive():
            pytest.fail(
                "_wait_child blocked past 10s on a child that sleeps for an hour; "
                "the suite killed it so this run would finish"
            )
        assert "error" in box, box
        assert "killed" in str(box["error"]).lower()
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            pass
        else:
            pytest.fail(f"child {pid} is still alive after _wait_child returned")
    finally:
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        try:
            os.waitpid(pid, 0)
        except ChildProcessError:
            pass
        worker.join(2)


@pytest.mark.parametrize("bad", BAD)
def test_intent_rejects_field_image_outside_images(tmp_path: Path, bad: str):
    path, secret = _show_dir(tmp_path, "images/field.png")
    value = _value(bad, secret, path.parent)
    _plant(path.parent, value)

    def check() -> None:
        client = _client(path)
        before = client.get("/api/show").json()
        response = client.post("/api/intent", json={"field_image": value})
        assert response.status_code == 422, response.text
        assert "field_image" in response.json()["detail"]
        assert client.get("/api/show").json() == before
        served = client.get("/api/field-image")
        assert served.status_code == 200
        assert served.content == PNG

    _unprivileged(tmp_path, check)


@pytest.mark.parametrize("bad", BAD)
def test_serve_404s_a_tampered_field_image_in_the_show_json(tmp_path: Path, bad: str):
    """Written straight into show.json, so the intent check never ran."""
    path, secret = _show_dir(tmp_path, None)
    value = _value(bad, secret, path.parent)
    _plant(path.parent, value)
    path.write_text(json.dumps({**load_show(path), "field_image": value}))

    def check() -> None:
        response = _client(path).get("/api/field-image")
        assert response.status_code == 404, bad
        assert SECRET not in response.content
        assert b"root:" not in response.content
        assert b"-planted" not in response.content

    _unprivileged(tmp_path, check)


@pytest.mark.parametrize("good", GOOD)
def test_boundary_names_are_accepted_and_served(tmp_path: Path, good: str):
    path, _ = _show_dir(tmp_path, None)
    _plant(path.parent, good)
    client = _client(path)
    assert client.post("/api/intent", json={"field_image": good}).status_code == 200
    served = client.get("/api/field-image")
    assert served.status_code == 200
    assert served.content == PNG + b"-planted"


def test_serve_404s_when_images_dir_points_outside_the_show(tmp_path: Path):
    show_dir = tmp_path / "show"
    show_dir.mkdir()
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (elsewhere / "field.png").write_bytes(SECRET)
    (show_dir / "images").symlink_to(elsewhere, target_is_directory=True)
    show = demo_show()
    show["field_image"] = "images/field.png"
    path = show_dir / "show.json"
    path.write_text(json.dumps(show))
    response = _client(path).get("/api/field-image")
    assert response.status_code == 404
    assert SECRET not in response.content


def test_legit_field_image_is_served_and_can_be_set_and_cleared(tmp_path: Path):
    path, _ = _show_dir(tmp_path, None)
    (path.parent / "images" / "yard.jpg").write_bytes(b"\xff\xd8\xffJPEG-yard")
    client = _client(path)
    assert client.get("/api/field-image").status_code == 404
    assert client.post("/api/intent", json={"field_image": "images/yard.jpg"}).status_code == 200
    served = client.get("/api/field-image")
    assert served.status_code == 200
    assert served.content == b"\xff\xd8\xffJPEG-yard"
    assert client.post("/api/intent", json={"field_image": None}).status_code == 200
    assert client.get("/api/field-image").status_code == 404


def test_upload_is_stored_as_a_marker_and_served(tmp_path: Path):
    path, _ = _show_dir(tmp_path, None)
    client = _client(path)
    upload = client.post("/api/image", files={"image": ("../../x.png", PNG + b"-upload", "image/png")})
    assert upload.status_code == 200
    assert upload.json()["field_image"] == "images/field.png"
    served = client.get("/api/field-image")
    assert served.content == PNG + b"-upload"
    assert (path.parent / "images" / "field.png").read_bytes() == PNG
    assert list(client.app.state.assets.rglob("upload*")) == []


def test_serve_404s_on_a_symlink_loop_or_unreadable_images_dir(tmp_path: Path):
    path, _ = _show_dir(tmp_path, "images/loop.png")
    images = path.parent / "images"
    (images / "loop.png").symlink_to("loop.png")
    client = _client(path)
    assert client.get("/api/field-image").status_code == 404
    if os.geteuid() == 0:
        pytest.skip("root ignores directory permissions")
    path.write_text(json.dumps({**load_show(path), "field_image": "images/field.png"}))
    client = _client(path)
    images.chmod(0)
    try:
        response = client.get("/api/field-image")
    finally:
        images.chmod(0o755)
    assert response.status_code == 404



def test_apply_intent_itself_refuses_a_bad_field_image():
    """``fieldshow apply`` has no HTTP handler in front of it, so this check stands alone."""
    show = demo_show()
    for bad in ("../x.png", "/etc/passwd", "images/x.txt", "images/\u212a.png", 7):
        with pytest.raises(ValueError, match="field_image"):
            apply_intent(show, {"field_image": bad})
    assert apply_intent(show, {"field_image": "images/field.png"})["field_image"] == "images/field.png"
    assert apply_intent(show, {"field_image": None})["field_image"] is None


def test_cli_import_image_writes_beside_the_output_not_cwd(tmp_path: Path):
    out_dir = tmp_path / "out"
    elsewhere = tmp_path / "cwd"
    out_dir.mkdir()
    elsewhere.mkdir()
    src = tmp_path / "pic.png"
    src.write_bytes(PNG)
    show = out_dir / "show.json"
    show.write_text(json.dumps(demo_show()))
    run = subprocess.run(
        [sys.executable, "-m", "fieldshow", "import-image", str(show), str(src), "-o", str(show)],
        cwd=elsewhere,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")},
    )
    assert run.returncode == 0, run.stderr
    assert (out_dir / "images" / "field.png").read_bytes() == PNG
    assert not (elsewhere / "images").exists()
    assert load_show(show)["field_image"] == "images/field.png"


def test_non_image_upload_is_415_and_leaves_the_show(tmp_path: Path):
    path, _ = _show_dir(tmp_path, "images/field.png")
    client = _client(path)
    before = client.get("/api/show").json()
    response = client.post("/api/image", files={"image": ("evil.exe", b"MZ", "application/octet-stream")})
    assert response.status_code == 415
    assert client.get("/api/show").json() == before
    assert client.get("/api/field-image").content == PNG
    assert list(client.app.state.assets.rglob("upload*")) == []


def test_scratch_is_removed_when_import_fails_after_the_write(tmp_path: Path, monkeypatch):
    """The scratch file exists once the body is written. Any later failure must still remove it."""
    import fieldshow.web.app as web_app

    def refuse(*_args, **_kwargs):
        raise ValueError("field image must be png, jpg, webp, or gif")

    monkeypatch.setattr(web_app, "import_image", refuse)
    path, _ = _show_dir(tmp_path, "images/field.png")
    client = _client(path)
    before = client.get("/api/show").json()
    response = client.post("/api/image", files={"image": ("field.png", PNG + b"-late", "image/png")})
    assert response.status_code == 415, response.text
    assert client.get("/api/show").json() == before
    assert list(client.app.state.assets.rglob("upload*")) == []


JPEG = b"\xff\xd8\xff" + b"JPEG-yard"
GIF87 = b"GIF87a" + b"gif-87"
GIF89 = b"GIF89a" + b"gif-89"
WEBP = b"RIFF" + b"\x24\x00\x00\x00" + b"WEBP" + b"webp-ok"

# Client filename is a lie on purpose. The stored marker has to follow the bytes.
SNIFFED = [
    ("yard", PNG + b"-bare", "images/field.png"),
    ("photo.png", JPEG, "images/field.jpg"),
    ("photo.jpeg", JPEG, "images/field.jpg"),
    ("anim.png", GIF87, "images/field.gif"),
    ("anim89.png", GIF89, "images/field.gif"),
    ("still.png", WEBP, "images/field.webp"),
    ("pic.gif", PNG + b"-as-gif", "images/field.png"),
    ("FIELD.PNG", PNG + b"-case", "images/field.png"),
]

NOT_AN_IMAGE = [
    ("notes", b"hello this is text"),
    ("fake.png", b"MZ-not-really"),
    ("sound.png", b"RIFF" + b"\x00\x00\x00\x00" + b"WAVE"),
    ("short.png", b"\x89PNG\r\n"),
    ("short.jpg", b"\xff\xd8"),
    ("nope.gif", b"GIF88a-nope"),
]


def _post_image(client: TestClient, filename: str, body: bytes):
    return client.post(
        "/api/image",
        files={"image": (filename, body, "application/octet-stream")},
    )


@pytest.mark.parametrize("filename,body,marker", SNIFFED)
def test_upload_stores_the_sniffed_type(tmp_path: Path, filename: str, body: bytes, marker: str):
    path, _ = _show_dir(tmp_path, None)
    show_png = path.parent / "images" / "field.png"
    client = _client(path)
    upload = _post_image(client, filename, body)
    assert upload.status_code == 200, upload.text
    assert upload.json()["field_image"] == marker
    assert client.get("/api/show").json()["field_image"] == marker
    assert client.get("/api/field-image").content == body
    assert show_png.read_bytes() == PNG
    stored = client.app.state.assets / marker
    assert stored.is_file()
    assert stored.read_bytes() == body
    assert list(client.app.state.assets.rglob("upload*")) == []


@pytest.mark.parametrize("filename,body", NOT_AN_IMAGE)
def test_upload_rejects_bytes_that_are_not_an_image(tmp_path: Path, filename: str, body: bytes):
    path, _ = _show_dir(tmp_path, "images/field.png")
    client = _client(path)
    before = client.get("/api/show").json()
    response = _post_image(client, filename, body)
    assert response.status_code == 415, response.text
    assert client.get("/api/show").json() == before
    assert client.get("/api/field-image").content == PNG
    assert list(client.app.state.assets.rglob("*")) == []


# 300 > NAME_MAX (255). A length cap is not the rule: evil.exe is short and still not an image suffix.
BAD_SUFFIX = [
    ("field." + "p" * 300, PNG + b"-long"),
    ("field." + "p" * 300, b"not-an-image"),
    ("evil.exe", PNG + b"-exe"),
]


@pytest.mark.parametrize("filename,body", BAD_SUFFIX)
def test_disallowed_suffix_is_415_before_anything_is_written(
    tmp_path: Path, filename: str, body: bytes
):
    path, _ = _show_dir(tmp_path, "images/field.png")
    client = _client(path)
    before = client.get("/api/show").json()
    response = _post_image(client, filename, body)
    assert response.status_code == 415, response.text
    assert client.get("/api/show").json() == before
    assert client.get("/api/field-image").content == PNG
    assert list(client.app.state.assets.rglob("*")) == []


def _without_blocking(fifo: Path, call) -> object:
    """Run ``call``; if it blocks opening the FIFO, unblock it and fail."""
    result: dict = {}
    worker = threading.Thread(target=lambda: result.setdefault("value", call()), daemon=True)
    worker.start()
    worker.join(5)
    if worker.is_alive():
        os.close(os.open(fifo, os.O_WRONLY | os.O_NONBLOCK))
        worker.join(5)
        pytest.fail("the server opened a FIFO named like an image")
    return result["value"]


def test_a_fifo_named_like_an_image_is_refused_without_blocking(tmp_path: Path):
    """``is_file`` is what refuses a FIFO; opening one would hang the request."""
    path, _ = _show_dir(tmp_path, None)
    fifo = path.parent / "images" / "pipe.png"
    os.mkfifo(fifo)
    client = _client(path)
    response = _without_blocking(fifo, lambda: client.post("/api/intent", json={"field_image": "images/pipe.png"}))
    assert response.status_code == 422
    path.write_text(json.dumps({**load_show(path), "field_image": "images/pipe.png"}))
    tampered = _client(path)
    assert _without_blocking(fifo, lambda: tampered.get("/api/field-image")).status_code == 404
