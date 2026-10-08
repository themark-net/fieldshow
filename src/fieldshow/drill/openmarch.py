"""Export a charted show to an OpenMarch .om document."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

# Goal to goal is 100 yards. 8 steps = 5 yards, so the goals sit at ±80 steps.
_GOAL_STEPS = 80
_YARD_LINE_STEPS = 8
_FRONT_HASH_STEPS = 32
# 160 feet / 22.5 inches = 256/3 steps from the front sideline to the back.
_BACK_SIDELINE_STEPS = 256 / 3


def export_om(show: dict) -> dict:
    counts = int(show["counts_per_set"])
    sets = show.get("sets") or []
    performers = show.get("performers") or []
    pages = []
    for index, page in enumerate(sets):
        if index == 0:
            duration = 0
            start_beat = 0
        else:
            duration = counts
            start_beat = 1 + counts * (index - 1)
        pages.append(
            {
                "id": str(index),
                "duration": duration,
                "startBeatIndex": start_beat,
                "name": page.get("name") or f"Set {index + 1}",
            }
        )
    moving_beats = counts * max(len(pages) - 1, 0)
    coordinates = []
    exported_performers = []
    for number, person in enumerate(performers, start=1):
        exported_performers.append(
            {
                "id": number,
                "label": person["label"],
                "section": person["section"],
            }
        )
        positions = person.get("positions") or []
        for index, page in enumerate(pages):
            if index >= len(positions):
                raise ValueError(f"{person.get('id', person['label'])} is missing a set")
            spot = positions[index]
            coordinates.append(
                {
                    "marcherId": str(number),
                    "pageId": page["id"],
                    "xSteps": spot["x"],
                    "ySteps": spot["y"],
                    "rotation_degrees": spot.get("rotation", 0),
                }
            )
    return {
        "omSchemaVersion": "0.1.0",
        "metadata": {
            "performanceArea": _performance_area(),
            "createdAtUtc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "audioOffsetSeconds": 0,
            "info": {
                "title": str(show.get("title") or ""),
                "author": str(show.get("author") or ""),
                "school": str(show.get("school") or ""),
                "year": str(show.get("year") or ""),
            },
        },
        "performers": exported_performers,
        "pages": pages,
        "tempoSections": [
            {"tempo": 0, "numberOfBeats": 1},
            {"tempo": show["tempo"], "numberOfBeats": moving_beats},
        ],
        "coordinates": coordinates,
        "measures": _measures(show),
    }


def write_om(show: dict, path: str | Path) -> None:
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(export_om(show), indent=2) + "\n")


def _performance_area() -> dict:
    x_checkpoints = []
    for steps in range(-_GOAL_STEPS, _GOAL_STEPS + 1, _YARD_LINE_STEPS):
        yards_from_left = (steps + _GOAL_STEPS) * 5 // _YARD_LINE_STEPS
        yard = min(yards_from_left, 100 - yards_from_left)
        if steps == 0:
            name = "50 yard line"
        elif yard == 0:
            name = "Left goal line" if steps < 0 else "Right goal line"
        else:
            name = f"{yard} yard line"
        x_checkpoints.append(
            {
                "name": name,
                "terseName": str(yard),
                "useAsReference": True,
                "fieldLabel": str(yard),
                "visible": True,
                "stepsFromCenter": steps,
            }
        )
    back_hash = _BACK_SIDELINE_STEPS - _FRONT_HASH_STEPS
    y_checkpoints = []
    for name, terse, label, steps in (
        ("Front sideline", "FSL", "0", 0),
        ("Front hash", "FH", "FH", _FRONT_HASH_STEPS),
        ("Back hash", "BH", "BH", back_hash),
        ("Back sideline", "BSL", "BSL", _BACK_SIDELINE_STEPS),
    ):
        y_checkpoints.append(
            {
                "name": name,
                "terseName": terse,
                "useAsReference": True,
                "fieldLabel": label,
                "visible": True,
                "stepsFromYOrigin": steps,
            }
        )
    return {
        "yOrigin": "front",
        "inchesPerStep": 22.5,
        "xCheckpoints": x_checkpoints,
        "yCheckpoints": y_checkpoints,
        "widthFeet": 360,
        "heightFeet": 160,
        "useHashes": True,
    }


def _measures(show: dict) -> list[dict]:
    melody = show.get("melody") or []
    if melody:
        length = len(melody)
    else:
        parts = show.get("parts") or {}
        lengths = [len(notes) for notes in parts.values() if isinstance(notes, list)]
        length = max(lengths) if lengths else 0
    meter = show.get("meter") or [4, 4]
    if not isinstance(meter, list) or not meter:
        return []
    beats_per_bar = int(meter[0])
    if beats_per_bar < 1 or length < 1:
        return []
    return [
        {"startBeatIndex": 1 + bar * beats_per_bar, "name": f"Measure {bar + 1}"}
        for bar in range(length // beats_per_bar)
    ]
