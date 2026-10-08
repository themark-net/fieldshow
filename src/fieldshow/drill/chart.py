"""Place marchers from line, block, and arc shapes. See docs/ARCHITECTURE.md."""

from __future__ import annotations

import copy
import math

from fieldshow.model import PREFIX, validate_intent


def chart(show: dict) -> dict:
    problems = validate_intent(show)
    if problems:
        raise ValueError("; ".join(problems))
    out = copy.deepcopy(show)
    placed = [_positions_by_section(page) for page in out["sets"]]
    counts = {section: len(points) for section, points in placed[0].items()}
    for page in placed[1:]:
        totals = {section: len(points) for section, points in page.items()}
        if totals != counts:
            raise ValueError("section counts must match across sets")
    # Section index follows first-set shape order. Later sets reuse that index.
    order: list[tuple[str, int]] = []
    next_index: dict[str, int] = {}
    for shape in out["sets"][0].get("shapes") or []:
        section = shape["section"]
        for _ in _place(shape):
            index = next_index.get(section, 0)
            next_index[section] = index + 1
            order.append((section, index))
    performers = []
    for section, index in order:
        number = index + 1
        positions = []
        for page in placed:
            x, y = page[section][index]
            positions.append({"x": x, "y": y, "rotation": 0})
        performers.append(
            {
                "id": f"{section}-{number}",
                "label": f"{PREFIX[section]}{number}",
                "section": section,
                "positions": positions,
            }
        )
    out["performers"] = performers
    return out


def interpolate(show: dict, beat: float) -> list[dict]:
    counts = show["counts_per_set"]
    frames = []
    for person in show.get("performers") or []:
        x, y, rotation = _at(person["positions"], beat, counts)
        frames.append(
            {
                "id": person["id"],
                "label": person["label"],
                "section": person["section"],
                "x": x,
                "y": y,
                "rotation": rotation,
            }
        )
    return frames


def _positions_by_section(page: dict) -> dict[str, list[tuple[float, float]]]:
    placed: dict[str, list[tuple[float, float]]] = {}
    for shape in page.get("shapes") or []:
        placed.setdefault(shape["section"], []).extend(_place(shape))
    return placed


def _place(shape: dict) -> list[tuple[float, float]]:
    kind = shape["kind"]
    if kind == "line":
        return _spread(shape["from"], shape["to"], int(shape["count"]))
    if kind == "block":
        origin_x, origin_y = shape["origin"]
        spacing = shape["spacing"]
        points = []
        for row in range(int(shape["rows"])):
            for col in range(int(shape["cols"])):
                points.append((origin_x + col * spacing, origin_y + row * spacing))
        return points
    if kind == "arc":
        center_x, center_y = shape["center"]
        radius = shape["radius"]
        count = int(shape["count"])
        if count <= 0:
            return []
        start = shape["start_deg"]
        end = shape["end_deg"]
        if count == 1:
            degrees = [start]
        else:
            span = count - 1
            degrees = [start + (end - start) * i / span for i in range(count)]
        points = []
        for degree in degrees:
            radians = math.radians(degree)
            points.append(
                (center_x + radius * math.cos(radians), center_y + radius * math.sin(radians))
            )
        return points
    raise ValueError(f"unknown shape {kind}")


def _spread(start, end, count: int) -> list[tuple[float, float]]:
    x0, y0 = start
    x1, y1 = end
    if count <= 0:
        return []
    if count == 1:
        return [(x0, y0)]
    span = count - 1
    return [
        (x0 + (x1 - x0) * i / span, y0 + (y1 - y0) * i / span) for i in range(count)
    ]


def _at(positions: list[dict], beat: float, counts: int) -> tuple[float, float, float]:
    if not positions:
        raise ValueError("performer has no positions")
    last = len(positions) - 1
    if last == 0 or beat <= 0:
        pos = positions[0]
        return pos["x"], pos["y"], pos.get("rotation", 0)
    span = counts * last
    if beat >= span:
        pos = positions[last]
        return pos["x"], pos["y"], pos.get("rotation", 0)
    index = int(beat // counts)
    if index >= last:
        pos = positions[last]
        return pos["x"], pos["y"], pos.get("rotation", 0)
    frac = (beat - index * counts) / counts
    start = positions[index]
    end = positions[index + 1]
    return (
        start["x"] + (end["x"] - start["x"]) * frac,
        start["y"] + (end["y"] - start["y"]) * frac,
        start.get("rotation", 0) + (end.get("rotation", 0) - start.get("rotation", 0)) * frac,
    )
