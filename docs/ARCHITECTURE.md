# Architecture

Fieldshow is the input glue around two open-source contracts:

- [music21](https://github.com/cuthbertLab/music21) (BSD-3) turns a lead sheet into MusicXML and MIDI.
- [OpenMarch/schema](https://github.com/OpenMarch/schema) (Apache-2.0) is the drill interchange file (`.om`). The OpenMarch desktop app is AGPL and is not vendored. A `.om` file opens there.

An agent (Grok Build, or anything that can write JSON) does the creative step. The process never calls a model. `fieldshow prompt-card` prints the JSON the agent must fill. `fieldshow apply`, `build`, and `serve` turn that JSON into parts, dots, and one page that shows all three.

```
intent JSON + optional image + optional MusicXML
        |  fieldshow apply / import-musicxml / import-image
        v
   show document (examples/fanfare.json is the sample)
        |-- arrange() --> parts, MusicXML, MIDI, playback JSON
        |-- chart()   --> marcher positions
        |-- export_om() --> OpenMarch .om
        v
   serve  -> one page: field, scrubber, parts, uniform and flag
```

## Show document

`version` is 1. `melody` is one token per beat (`Bb4`, `F#5`, `C4`). `chords` is one symbol per measure (`Bb`, `F7`, `Gm`, `Cmaj7`). `meter` is `[beats, beat-value]`. `sets[].shapes` place sections. `design` is optional and holds `uniform`, `flag`, and `palette` (2 to 6 `#rrggbb` colors). `field_image` is a path or null. `performers` and `parts` are filled by `chart` and `arrange`.

`validate_intent` in `model.py` is the gate. Do not accept a show it rejects.

## Spelling

music21 prints flats as `B-`. Fieldshow spells them with a `b`:

```python
def spell(p) -> str:
    return f"{p.name.replace('-', 'b')}{p.octave}"
```

`Bb4` stays `Bb4`. Use this for `parts` and for `import_musicxml` melody tokens. Key names use the same letter style (`Bb`, not `B-`).

## Arrangement (`music/arrange.py`, `music/io.py`)

`arrange(show)` copies the show and sets `parts` for every section below, each a list of note tokens or `None` for a rest, one entry per melody beat. Call `validate_intent` and raise `ValueError` on problems. Parse chords with `music21.harmony.ChordSymbol` after rewriting a flat root into music21's spelling (`Bb` becomes `B-`, `Eb` becomes `E-`). If the symbol has no root, raise `ValueError`. `ChordSymbol.third` and `.fifth` may already sit in some other octave (`F7`'s third comes back as `A2`). Build a new `Pitch` with that note name and force the octave in the table below. Do not keep the octave music21 picked.

Voices, before transposition:

| Section | Concert voice |
| --- | --- |
| flute, clarinet, trumpet, mellophone | the melody note |
| alto_sax, baritone | chord fifth, forced into octave 3 |
| tenor_sax, trombone | chord third, forced into octave 3 |
| tuba | chord root, forced into octave 2 |

Transposition after the concert voice is chosen, in semitones: flute 0, clarinet 2, alto_sax 9, tenor_sax 2, trumpet 2, mellophone 7, trombone 0, baritone 0, tuba 0. `Pitch.transpose(n)` does this. Then `spell`.

Battery ignores chords. In 4/4, and for any meter, repeat this beat pattern across the melody:

- snare: accent, tap, accent, tap → `C5`, `G4`, `C5`, `G4`
- bass drum: hit, rest, rest, rest → `C4`, `None`, `None`, `None`

The pattern restarts every 4 beats. A 3/4 tune still uses the first three cells of that pattern in each bar of three, then restarts. For the demo meter this is the whole pattern.

`playback(show)` returns one object per section, in `SECTION_ORDER`. Each note is `{beat, midi, beats}` with `beats` 1. Omit rests. `beat` is the index in the part list.

`export_musicxml` writes one score. Part order is `SECTION_ORDER`. `partName` values are Flute, Clarinet, Alto Sax, Tenor Sax, Trumpet, Mellophone, Trombone, Baritone, Tuba, Snare, Bass Drum. Key signature comes from `show["key"]` via `music21.key.Key` (`Bb` is two flats, `sharps == -2`). Time signature from `meter`. Quarter notes, and rests where the token is `None`. `export_midi` writes a playable MIDI file of those same parts.

`import_musicxml` reads the first part's notes into `melody` (rests dropped), copies that part's meter and key, and sets `chords` to `"C"` repeated once per measure. Other show fields can be the demo defaults. The result must pass `validate_intent` after a caller adds sets, or it may include the demo sets so a bare import is already a valid intent. Prefer copying `demo_show()` and replacing melody, key, meter, tempo (if present), and chords.

## Drill (`drill/chart.py`, `drill/openmarch.py`)

Coordinates are steps. `x` is from the 50 yard line, negative toward audience left. `y` is steps from the front sideline toward the backfield. 8 steps = 5 yards. One step = 22.5 inches.

`chart(show)` replaces `performers`. Section sizes come from the shapes. The same section must have the same total count on every set; otherwise raise `ValueError`.

Shape kinds:

- `line`: `count` marchers from `from` to `to`, both ends included. One marcher stays on `from`.
- `block`: `rows` by `cols`, row-major. Column steps in `+x`, row steps in `+y`, from `origin`, by `spacing`.
- `arc`: `count` marchers from `start_deg` to `end_deg`. 0 degrees is `+x`. Standard math angles. `y` still grows toward the backfield. `x = cx + r cos`, `y = cy + r sin`. Ends included.

Labels use `PREFIX` from `model.py` plus a section index starting at 1, in first-set shape order, and in geometric order inside the shape. Later sets reuse that same person for the same section index. `id` is `{section}-{n}` such as `trumpet-1`. Each performer:

```json
{"id": "trumpet-1", "label": "T1", "section": "trumpet",
 "positions": [{"x": -16, "y": 32, "rotation": 0}, {"x": 0, "y": 0, "rotation": 0}]}
```

One position per set. `rotation` is 0 in this version (facing the front sideline).

`interpolate(show, beat)` returns `{id, label, section, x, y, rotation}` for every performer. Sets sit at beats `0, counts_per_set, 2 * counts_per_set, ...`. Between two sets, positions move in a straight line. On a set's beat, return that set. Before the first or after the last, clamp.

`export_om(show)` returns a document that validates against `src/fieldshow/data/openmarch-schema.json`. Required shape:

- `omSchemaVersion` `"0.1.0"`
- `metadata.createdAtUtc` an ISO timestamp, `metadata.audioOffsetSeconds` 0, `metadata.info` title/author/school/year
- `metadata.performanceArea`: `yOrigin` `"front"`, `inchesPerStep` 22.5, `useHashes` true, `widthFeet` 360, `heightFeet` 160
- x checkpoints include the 50 yard line at `stepsFromCenter` 0 with `"50"` in the name. Yard lines run from audience-left goal (`-80`) to audience-right goal (`80`) every 8 steps.
- y checkpoints include the front hash at `stepsFromYOrigin` 32, the front sideline at 0, and the back sideline at `256/3` (85 and 1/3 steps).
- performers: numeric `id` starting at 1, plus `label` and `section`
- pages: one per set. Page 0 has `duration` 0 and `startBeatIndex` 0. Each later page has `duration` `counts_per_set`. The second page starts at beat index 1 because the opening OpenMarch beat is the zero-tempo beat.
- `tempoSections`: `{"tempo": 0, "numberOfBeats": 1}` then `{"tempo": <show tempo>, "numberOfBeats": <counts_per_set * (pages - 1)>}`. The sum of `numberOfBeats` is `1 + counts_per_set * (n_sets - 1)`.
- `measures`: one per bar of the melody when `parts` or `melody` exist. `startBeatIndex` starts at 1 and steps by `meter[0]`. Demo values are 1 and 5.
- `coordinates`: every marcher on every page. `marcherId` is the string form of the numeric performer id. `pageId` matches that page's id. `xSteps` and `ySteps` come from `positions`.

`write_om` writes that dict as JSON.

`drill/image.py` is already implemented. Leave it.

## Web (`web/app.py` and `web/static/index.html`)

`create_app(show)` returns a FastAPI app. It arranges and charts the show on startup and after each intent. One in-memory show.

- `GET /` HTML page that contains the show title and `<input type="range">`.
- `GET /api/health` → `{"ok": true}`
- `GET /api/show` the built show
- `GET /api/frame?beat=` interpolated positions, plus `beat` and `tempo`
- `GET /api/playback` the playback list
- `POST /api/intent` JSON merge via `apply_intent`, then arrange and chart again
- `POST /api/image` multipart field `image`, stored with `import_image`, path kept on the show
- `GET /api/field-image` the stored bytes, or 404

The page draws the football field, dots colored from the palette by section, the scrubber, the part names, and the uniform and flag text. Scrubbing calls `/api/frame`. No frontend build. Dark page, accent `#e8a838`.

## What is not inside this process

No model weights, no FluidSynth, no MuseScore, no OpenMarch Electron app. PDF engraving and audio transcription are open questions.
