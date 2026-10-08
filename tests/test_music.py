"""Behavior spec for the arranger. Failures here are the bug."""

from pathlib import Path

from music21 import converter, pitch

from fieldshow.model import demo_show
from fieldshow.music.arrange import arrange, playback
from fieldshow.music.io import export_midi, export_musicxml, import_musicxml


def _midi(name: str) -> int:
    return pitch.Pitch(name).midi


def test_transposed_block_voicing_and_battery():
    show = arrange(demo_show())
    parts = show["parts"]
    assert list(parts) == [
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
    assert parts["flute"][0] == "Bb4"
    assert parts["trumpet"][0] == "C5"
    assert parts["mellophone"][0] == "F5"
    assert parts["clarinet"][0] == "C5"
    # Fifth of Bb in octave 3, then Eb alto transposition (up a major sixth).
    assert parts["alto_sax"][0] == "D4"
    # Third of Bb in octave 3, then Bb transposition.
    assert parts["tenor_sax"][0] == "E3"
    assert parts["trombone"][0] == "D3"
    assert parts["baritone"][0] == "F3"
    assert parts["tuba"][0] == "Bb2"
    assert parts["tuba"][4] == "F2"
    assert parts["trombone"][4] == "A3"
    assert parts["snare"][:4] == ["C5", "G4", "C5", "G4"]
    assert parts["bass_drum"][:4] == ["C4", None, None, None]
    assert all(len(notes) == 8 for notes in parts.values())


def test_musicxml_and_midi_round_trip(tmp_path: Path):
    show = arrange(demo_show())
    xml_path = tmp_path / "fanfare.musicxml"
    mid_path = tmp_path / "fanfare.mid"
    export_musicxml(show, xml_path)
    export_midi(show, mid_path)
    assert mid_path.stat().st_size > 50
    score = converter.parse(xml_path)
    assert score.parts[4].partName == "Trumpet"
    trumpet = list(score.parts[4].flatten().notes)
    assert trumpet[0].pitch.midi == _midi("C5")
    assert score.parts[8].partName == "Tuba"
    tuba = list(score.parts[8].flatten().notes)
    assert tuba[0].pitch.midi == _midi("Bb2")
    assert tuba[4].pitch.midi == _midi("F2")
    signature = score.parts[0].flatten().getElementsByClass("KeySignature")[0]
    assert signature.sharps == -2
    imported = import_musicxml(xml_path)
    assert imported["melody"][0] == "Bb4"
    assert imported["meter"] == [4, 4]
    assert imported["key"] == "Bb"


def test_playback_skips_bass_drum_rests():
    show = arrange(demo_show())
    events = {item["part"]: item["notes"] for item in playback(show)}
    bass = events["bass_drum"]
    assert bass[0]["beat"] == 0
    assert bass[0]["midi"] == _midi("C4")
    assert all(note["beat"] % 4 == 0 for note in bass)
    assert events["trumpet"][0]["midi"] == _midi("C5")
    assert events["trumpet"][0]["beats"] == 1


def test_bad_chord_fails():
    show = demo_show()
    show["chords"] = ["Bb", "not-a-chord"]
    try:
        arrange(show)
    except ValueError:
        return
    raise AssertionError("unknown chord should fail")
