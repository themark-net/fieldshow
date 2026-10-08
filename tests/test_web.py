"""Integrated server: one show, music, drill, and design on one page."""

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
