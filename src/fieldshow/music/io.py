"""MusicXML and MIDI writers and the MusicXML importer."""

from __future__ import annotations

from pathlib import Path

from music21 import converter, key, meter, note, pitch, stream, tempo

from fieldshow.model import SECTION_ORDER, demo_show
from fieldshow.music.arrange import spell

_PART_NAMES = {
    "flute": "Flute",
    "clarinet": "Clarinet",
    "alto_sax": "Alto Sax",
    "tenor_sax": "Tenor Sax",
    "trumpet": "Trumpet",
    "mellophone": "Mellophone",
    "trombone": "Trombone",
    "baritone": "Baritone",
    "tuba": "Tuba",
    "snare": "Snare",
    "bass_drum": "Bass Drum",
}


def export_musicxml(show: dict, path: str | Path) -> None:
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    _score(show).write("musicxml", fp=str(dest))


def export_midi(show: dict, path: str | Path) -> None:
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    _score(show).write("midi", fp=str(dest))


def import_musicxml(path: str | Path) -> dict:
    """Lead sheet from the first part. Rests are dropped. Chords become ``C``."""
    score = converter.parse(str(path))
    part = score.parts[0]
    flat = part.flatten()
    melody = [spell(_first_pitch(n)) for n in flat.notes]
    time_signatures = list(flat.getElementsByClass("TimeSignature"))
    if time_signatures:
        show_meter = [int(time_signatures[0].numerator), int(time_signatures[0].denominator)]
    else:
        show_meter = [4, 4]
    signatures = list(flat.getElementsByClass("KeySignature"))
    key_name = _key_name(signatures[0]) if signatures else "C"
    show = demo_show()
    show["melody"] = melody
    show["key"] = key_name
    show["meter"] = show_meter
    beats = show_meter[0]
    bars = len(melody) // beats if beats and melody and len(melody) % beats == 0 else 0
    if bars:
        show["chords"] = ["C"] * bars
    marks = list(flat.getElementsByClass("MetronomeMark"))
    if not marks:
        marks = list(score.flatten().getElementsByClass("MetronomeMark"))
    if marks and marks[0].number:
        number = float(marks[0].number)
        show["tempo"] = int(number) if number.is_integer() else number
    return show


def _score(show: dict) -> stream.Score:
    score = stream.Score()
    key_name = show.get("key") or "C"
    beats, beat_value = show.get("meter") or [4, 4]
    tempo_number = show.get("tempo")
    parts = show.get("parts") or {}
    for section in SECTION_ORDER:
        part = stream.Part()
        part.partName = _PART_NAMES[section]
        # Fresh objects per part. music21 will not insert the same element twice.
        part.insert(0, _signature(key_name))
        part.insert(0, meter.TimeSignature(f"{beats}/{beat_value}"))
        if tempo_number:
            part.insert(0, tempo.MetronomeMark(number=tempo_number))
        for token in parts.get(section) or []:
            if token is None:
                part.append(note.Rest(quarterLength=1.0))
            else:
                part.append(note.Note(token, quarterLength=1.0))
        score.append(part)
    return score


def _signature(name: str) -> key.Key:
    """Major key. ``Bb`` is two flats, which music21 spells ``B-``."""
    return key.Key(name.replace("b", "-"))


def _key_name(signature: key.KeySignature) -> str:
    if isinstance(signature, key.Key):
        tonic = signature.tonic
    else:
        tonic = signature.asKey("major").tonic
    return tonic.name.replace("-", "b")


def _first_pitch(n) -> pitch.Pitch:
    pitches = getattr(n, "pitches", None)
    if pitches:
        return pitches[0]
    return n.pitch
