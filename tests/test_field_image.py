"""field_image is only ever a file under images/ in the show dir or the upload dir (#3)."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from fieldshow.model import demo_show, load_show
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


BAD = [
    "../secret.png",
    "images/../../secret.png",
    "%2e%2e%2fsecret.png",
    "images/%2e%2e%2f%2e%2e%2fsecret.png",
    "/etc/passwd",
    "SECRET_ABS",
    "images/out.png",
    "images/field.png\x00",
    "show.json",
    "images/missing.png",
]


def _value(bad: str, secret: Path) -> str:
    return str(secret) if bad == "SECRET_ABS" else bad


@pytest.mark.parametrize("bad", BAD)
def test_intent_rejects_field_image_outside_images(tmp_path: Path, bad: str):
    path, secret = _show_dir(tmp_path, "images/field.png")
    client = _client(path)
    before = client.get("/api/show").json()
    response = client.post("/api/intent", json={"field_image": _value(bad, secret)})
    assert response.status_code == 422, response.text
    assert "field_image" in response.json()["detail"]
    assert client.get("/api/show").json() == before
    served = client.get("/api/field-image")
    assert served.status_code == 200
    assert served.content == PNG


@pytest.mark.parametrize("bad", BAD)
def test_serve_404s_a_tampered_field_image_in_the_show_json(tmp_path: Path, bad: str):
    """Written straight into show.json, so the intent check never ran."""
    path, secret = _show_dir(tmp_path, _value(bad, secret_path := tmp_path / "secret.png"))
    assert secret == secret_path
    response = _client(path).get("/api/field-image")
    assert response.status_code == 404, bad
    assert SECRET not in response.content
    assert b"root:" not in response.content


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


@pytest.mark.parametrize("odd", ["ABS_LEGIT", "images/./field.png", "images/x/../field.png", "images//field.png"])
def test_non_canonical_markers_are_refused_even_if_they_land_on_the_real_image(tmp_path: Path, odd: str):
    """Only the exact images/<name>.<ext> marker is honoured, at intent and at serve."""
    path, _ = _show_dir(tmp_path, None)
    value = str(path.parent / "images" / "field.png") if odd == "ABS_LEGIT" else odd
    response = _client(path).post("/api/intent", json={"field_image": value})
    assert response.status_code == 422, response.text
    path.write_text(json.dumps({**load_show(path), "field_image": value}))
    assert _client(path).get("/api/field-image").status_code == 404
