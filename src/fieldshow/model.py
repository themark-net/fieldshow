"""Show document. This JSON is the agent input language."""

from __future__ import annotations

import copy
import json
from pathlib import Path

from music21 import pitch

SECTION_ORDER = [
    "flute",
    "clarinet",
    "alto_sax",
    "tenor_sax",
    "trumpet",
    "mellophone",
    "trombone",
    "baritone",
    "tuba",
    "snare",
    "bass_drum",
]

PREFIX = {
    "flute": "F",
    "clarinet": "C",
    "alto_sax": "A",
    "tenor_sax": "N",
    "trumpet": "T",
    "mellophone": "M",
    "trombone": "R",
    "baritone": "B",
    "tuba": "U",
    "snare": "S",
    "bass_drum": "D",
}


def demo_show() -> dict:
    """Original 8-beat fanfare. Not a copyrighted tune."""
    return {
        "version": 1,
        "title": "Gate Fanfare",
        "author": "fieldshow",
        "school": "",
        "year": "2026",
        "key": "Bb",
        "meter": [4, 4],
        "tempo": 132,
        "melody": ["Bb4", "D5", "F5", "Bb5", "A5", "G5", "F5", "Eb5"],
        "chords": ["Bb", "F7"],
        "ensemble": "hs-wind-battery",
        "counts_per_set": 8,
        "sets": [
            {
                "name": "Hash line",
                "shapes": [
                    {
                        "section": "trumpet",
                        "kind": "line",
                        "from": [-16, 32],
                        "to": [16, 32],
                        "count": 5,
                    },
                    {
                        "section": "tuba",
                        "kind": "block",
                        "origin": [-6, 12],
                        "rows": 2,
                        "cols": 2,
                        "spacing": 2,
                    },
                    {
                        "section": "snare",
                        "kind": "line",
                        "from": [-4, 20],
                        "to": [4, 20],
                        "count": 3,
                    },
                ],
            },
            {
                "name": "Spread",
                "shapes": [
                    {
                        "section": "trumpet",
                        "kind": "arc",
                        "center": [0, 28],
                        "radius": 14,
                        "start_deg": 200,
                        "end_deg": 340,
                        "count": 5,
                    },
                    {
                        "section": "tuba",
                        "kind": "line",
                        "from": [-18, 8],
                        "to": [18, 8],
                        "count": 4,
                    },
                    {
                        "section": "snare",
                        "kind": "line",
                        "from": [-6, 18],
                        "to": [6, 18],
                        "count": 3,
                    },
                ],
            },
        ],
        "design": {
            "uniform": "Black jacket, gold sash",
            "flag": "Gold field with a black diagonal",
            "palette": ["#e8a838", "#14120e", "#f4efe4", "#8c3a3a"],
        },
        "field_image": None,
        "performers": [],
        "parts": {},
    }


def load_show(path: str | Path) -> dict:
    return json.loads(Path(path).read_text())


def save_show(show: dict, path: str | Path) -> None:
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(show, indent=2) + "\n")


def apply_intent(show: dict, intent: dict) -> dict:
    """Merge an agent intent over a show. Shallow on known keys, replace sets."""
    out = copy.deepcopy(show)
    for key in (
        "title",
        "author",
        "school",
        "year",
        "key",
        "meter",
        "tempo",
        "melody",
        "chords",
        "ensemble",
        "counts_per_set",
        "sets",
        "design",
        "field_image",
    ):
        if key in intent:
            out[key] = copy.deepcopy(intent[key])
    problems = validate_intent(out)
    if problems:
        raise ValueError("; ".join(problems))
    return out


def _shape_count(shape: dict) -> int:
    if shape["kind"] == "block":
        return int(shape["rows"]) * int(shape["cols"])
    return int(shape["count"])


def validate_intent(show: dict) -> list[str]:
    problems: list[str] = []
    if show.get("version") != 1:
        problems.append("version must be 1")
    meter = show.get("meter")
    if (
        not isinstance(meter, list)
        or len(meter) != 2
        or meter[1] not in (1, 2, 4, 8, 16)
        or not isinstance(meter[0], int)
        or meter[0] < 1
    ):
        problems.append("meter must be [beats, beat-value]")
        beats_per_bar = None
    else:
        beats_per_bar = meter[0]
    melody = show.get("melody") or []
    chords = show.get("chords") or []
    if beats_per_bar and (not melody or len(melody) % beats_per_bar):
        problems.append("melody length must be a whole number of bars")
    if beats_per_bar and melody and len(chords) != len(melody) // beats_per_bar:
        problems.append("one chord per measure")
    for note in melody:
        try:
            pitch.Pitch(note)
        except Exception:
            problems.append(f"bad melody note {note}")
    if not isinstance(show.get("tempo"), (int, float)) or show.get("tempo", 0) <= 0:
        problems.append("tempo must be a positive number")
    counts = show.get("counts_per_set")
    if not isinstance(counts, int) or counts < 1:
        problems.append("counts_per_set must be a positive integer")
    sets = show.get("sets") or []
    if len(sets) < 1:
        problems.append("at least one set")
    counts_by_section: dict[str, int] | None = None
    for page in sets:
        totals: dict[str, int] = {}
        for shape in page.get("shapes") or []:
            section = shape.get("section")
            if section not in PREFIX:
                problems.append(f"unknown section {section}")
                continue
            try:
                totals[section] = totals.get(section, 0) + _shape_count(shape)
            except Exception:
                problems.append(f"bad shape in {page.get('name')}")
        if counts_by_section is None:
            counts_by_section = totals
        elif totals != counts_by_section:
            problems.append("section counts must match across sets")
            break
    return problems
