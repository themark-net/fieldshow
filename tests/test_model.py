import json
from pathlib import Path

from fieldshow.design import apply_design
from fieldshow.drill.image import import_image
from fieldshow.model import apply_intent, demo_show, validate_intent

ROOT = Path(__file__).resolve().parents[1]


def test_demo_file_matches_builder():
    saved = json.loads((ROOT / "examples" / "fanfare.json").read_text())
    assert saved == demo_show()


def test_demo_intent_is_valid():
    assert validate_intent(demo_show()) == []


def test_apply_replaces_melody_and_rejects_a_short_bar():
    show = apply_intent(demo_show(), {"title": "Night Gate", "tempo": 108})
    assert show["title"] == "Night Gate"
    assert show["tempo"] == 108
    try:
        apply_intent(show, {"melody": ["C4", "D4", "E4"]})
    except ValueError as exc:
        assert "melody" in str(exc)
    else:
        raise AssertionError("short melody should fail")


def test_design_palette_bounds():
    show = apply_design(demo_show(), {"uniform": "wool", "flag": "plain", "palette": ["#112233", "#abcdef"]})
    assert show["design"]["uniform"] == "wool"
    try:
        apply_design(show, {"palette": ["red"]})
    except ValueError:
        return
    raise AssertionError("named colors are not a palette")


def test_image_import_copies_a_png(tmp_path: Path):
    src = tmp_path / "yard.png"
    src.write_bytes(b"\x89PNG\r\n\x1a\n")
    show = import_image(demo_show(), src, tmp_path / "assets")
    copied = Path(show["field_image"])
    assert copied.is_file()
    assert copied.read_bytes().startswith(b"\x89PNG")
