"""Arrange a lead sheet into a high-school wind and battery score."""

from __future__ import annotations

import copy

from music21 import harmony, pitch

from fieldshow.model import SECTION_ORDER, validate_intent

# Concert voice, then the octave that voice is forced into. Melody keeps
# the written octave. Transposition is applied after that, in semitones.
_VOICE = {
    "flute": ("melody", None, 0),
    "clarinet": ("melody", None, 2),
    "alto_sax": ("fifth", 3, 9),
    "tenor_sax": ("third", 3, 2),
    "trumpet": ("melody", None, 2),
    "mellophone": ("melody", None, 7),
    "trombone": ("third", 3, 0),
    "baritone": ("fifth", 3, 0),
    "tuba": ("root", 2, 0),
}

# Four-cell battery cycle. A bar shorter than 4 uses the leading cells and
# restarts at the next barline; a longer bar restarts every 4 beats.
_SNARE = ("C5", "G4", "C5", "G4")
_BASS = ("C4", None, None, None)


def spell(p: pitch.Pitch) -> str:
    """Fieldshow note token. music21 prints flats as ``B-``; we use ``Bb``."""
    return f"{p.name.replace('-', 'b')}{p.octave}"


def arrange(show: dict) -> dict:
    """Copy ``show`` and fill ``parts`` for every section in ``SECTION_ORDER``."""
    problems = validate_intent(show)
    if problems:
        raise ValueError("; ".join(problems))
    out = copy.deepcopy(show)
    melody: list[str] = out["melody"]
    beats_per_bar = out["meter"][0]
    symbols = [_chord_symbol(figure) for figure in out["chords"]]
    parts: dict[str, list[str | None]] = {}
    for section in SECTION_ORDER:
        if section == "snare":
            parts[section] = [_cycle(_SNARE, i, beats_per_bar) for i in range(len(melody))]
            continue
        if section == "bass_drum":
            parts[section] = [_cycle(_BASS, i, beats_per_bar) for i in range(len(melody))]
            continue
        kind, octave, semitones = _VOICE[section]
        line: list[str | None] = []
        for index, token in enumerate(melody):
            symbol = symbols[index // beats_per_bar]
            sounded = _concert(kind, token, symbol, octave)
            line.append(spell(sounded.transpose(semitones)))
        parts[section] = line
    out["parts"] = parts
    return out


def playback(show: dict) -> list[dict]:
    """One event list per section. Rests are omitted. Each note lasts one beat."""
    parts = show.get("parts") or {}
    events = []
    for section in SECTION_ORDER:
        notes = []
        for beat, token in enumerate(parts.get(section) or []):
            if token is None:
                continue
            notes.append({"beat": beat, "midi": int(pitch.Pitch(token).midi), "beats": 1})
        events.append({"part": section, "notes": notes})
    return events


def _cycle(pattern: tuple, beat: int, beats_per_bar: int):
    cell = beat % beats_per_bar
    return pattern[cell % len(pattern)]


def _concert(kind: str, token: str, symbol: harmony.ChordSymbol, octave: int | None) -> pitch.Pitch:
    if kind == "melody":
        return pitch.Pitch(token)
    tone = _degree(symbol, kind)
    sounded = pitch.Pitch(tone.name)
    sounded.octave = octave
    return sounded


def _degree(symbol: harmony.ChordSymbol, kind: str) -> pitch.Pitch:
    if kind == "root":
        tone = symbol.root()
    elif kind == "third":
        tone = symbol.third
    else:
        tone = symbol.fifth
    if tone is None:
        raise ValueError(f"chord {symbol.figure} has no {kind}")
    return tone


def _chord_symbol(figure: str) -> harmony.ChordSymbol:
    """Parse a fieldshow chord (``Bb``, ``F7``). music21 wants ``B-`` for flats."""
    token = _flats_for_music21(figure)
    try:
        symbol = harmony.ChordSymbol(token)
    except Exception as exc:
        raise ValueError(f"bad chord {figure}") from exc
    if symbol.root() is None:
        raise ValueError(f"bad chord {figure}")
    return symbol


def _flats_for_music21(figure: str) -> str:
    out: list[str] = []
    index = 0
    while index < len(figure):
        if (
            index + 1 < len(figure)
            and figure[index] in "ABCDEFG"
            and figure[index + 1] == "b"
        ):
            out.append(figure[index])
            out.append("-")
            index += 2
            continue
        out.append(figure[index])
        index += 1
    return "".join(out)
