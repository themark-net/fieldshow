"""Behavior spec for drill geometry and the OpenMarch export."""

import json
import math
from pathlib import Path

import jsonschema

from fieldshow.drill.chart import chart, interpolate
from fieldshow.drill.openmarch import export_om
from fieldshow.model import demo_show

SCHEMA = json.loads(
    Path(__file__).resolve().parents[1].joinpath("src/fieldshow/data/openmarch-schema.json").read_text()
)


def _by_label(show: dict, label: str) -> dict:
    return next(person for person in show["performers"] if person["label"] == label)


def test_line_block_and_arc_geometry():
    show = chart(demo_show())
    assert len(show["performers"]) == 12
    trumpet = _by_label(show, "T1")
    assert trumpet["section"] == "trumpet"
    assert trumpet["positions"][0]["x"] == -16
    assert trumpet["positions"][0]["y"] == 32
    end = _by_label(show, "T5")["positions"][0]
    assert end["x"] == 16 and end["y"] == 32
    tuba = _by_label(show, "U1")["positions"][0]
    assert (tuba["x"], tuba["y"]) == (-6, 12)
    tuba_far = _by_label(show, "U4")["positions"][0]
    assert (tuba_far["x"], tuba_far["y"]) == (-4, 14)
    spread = _by_label(show, "T1")["positions"][1]
    rad = math.radians(200)
    assert spread["x"] == 0 + 14 * math.cos(rad)
    assert spread["y"] == 28 + 14 * math.sin(rad)
    last = _by_label(show, "T5")["positions"][1]
    rad = math.radians(340)
    assert last["x"] == 14 * math.cos(rad)
    assert last["y"] == 28 + 14 * math.sin(rad)
    assert all(pos["rotation"] == 0 for person in show["performers"] for pos in person["positions"])


def test_interpolate_midpoint():
    show = chart(demo_show())
    opening = {person["id"]: person for person in interpolate(show, 0)}
    middle = {person["id"]: person for person in interpolate(show, 4)}
    person = _by_label(show, "T1")
    assert opening[person["id"]]["x"] == person["positions"][0]["x"]
    assert middle[person["id"]]["x"] == (
        person["positions"][0]["x"] + person["positions"][1]["x"]
    ) / 2
    assert middle[person["id"]]["y"] == (
        person["positions"][0]["y"] + person["positions"][1]["y"]
    ) / 2


def test_section_count_mismatch_fails():
    show = demo_show()
    show["sets"][1]["shapes"][0]["count"] = 4
    try:
        chart(show)
    except ValueError:
        return
    raise AssertionError("changing a section's size between sets should fail")


def test_openmarch_document_validates():
    show = chart(demo_show())
    document = export_om(show)
    jsonschema.validate(document, SCHEMA)
    area = document["metadata"]["performanceArea"]
    assert area["yOrigin"] == "front"
    assert area["inchesPerStep"] == 22.5
    assert any(item["stepsFromCenter"] == 0 and "50" in item["name"] for item in area["xCheckpoints"])
    assert any(item["stepsFromYOrigin"] == 32 for item in area["yCheckpoints"])
    assert document["tempoSections"][0] == {"tempo": 0, "numberOfBeats": 1}
    assert sum(section["numberOfBeats"] for section in document["tempoSections"]) == 9
    assert document["pages"][0]["duration"] == 0
    assert document["pages"][1]["duration"] == 8
    assert document["measures"][0]["startBeatIndex"] == 1
    assert document["measures"][1]["startBeatIndex"] == 5
    labels = {person["label"]: person["id"] for person in document["performers"]}
    opening = [
        dot
        for dot in document["coordinates"]
        if dot["pageId"] == document["pages"][0]["id"] and dot["marcherId"] == str(labels["T1"])
    ]
    assert len(opening) == 1
    assert opening[0]["xSteps"] == -16
    assert isinstance(opening[0]["marcherId"], str)
    assert len(document["coordinates"]) == 24
