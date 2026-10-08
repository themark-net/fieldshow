# Fieldshow prompt card

You are writing a marching show by filling JSON. Do not invent a new file format. Read `docs/ARCHITECTURE.md` if a field is unclear. The program arranges, places marchers, and draws the page. You supply the musical idea, the shapes, and the look.

## Write this intent

```json
{
  "title": "Gate Fanfare",
  "author": "your name",
  "key": "Bb",
  "meter": [4, 4],
  "tempo": 132,
  "melody": ["Bb4", "D5", "F5", "Bb5", "A5", "G5", "F5", "Eb5"],
  "chords": ["Bb", "F7"],
  "counts_per_set": 8,
  "sets": [
    {
      "name": "Hash line",
      "shapes": [
        {"section": "trumpet", "kind": "line", "from": [-16, 32], "to": [16, 32], "count": 5}
      ]
    }
  ],
  "design": {
    "uniform": "Black jacket, gold sash",
    "flag": "Gold field with a black diagonal",
    "palette": ["#e8a838", "#14120e", "#f4efe4"]
  }
}
```

Rules that keep the file valid:

- One melody token per beat. Note names look like `Bb4` or `F#5`.
- One chord per measure. `Bb`, `Gm`, `F7`, and `Cmaj7` are fine.
- `melody` length divides into bars of `meter[0]` beats.
- A section's marcher count is the same on every set.
- Sections: flute, clarinet, alto_sax, tenor_sax, trumpet, mellophone, trombone, baritone, tuba, snare, bass_drum.
- Shapes are `line` (`from`, `to`, `count`), `block` (`origin`, `rows`, `cols`, `spacing`), or `arc` (`center`, `radius`, `start_deg`, `end_deg`, `count`).
- Steps: x from the 50, negative to audience left. y from the front sideline toward the back. Front hash is y 32. Goal lines are x -80 and 80.
- Palette is 2 to 6 colors written `#rrggbb`.
- The tune must be original or in the public domain. Do not paste copyrighted melody.

## Commands

```bash
fieldshow apply intent.json -o show.json
fieldshow import-musicxml score.musicxml -o show.json
fieldshow import-image show.json field.png -o show.json
fieldshow export-musicxml show.json -o score.musicxml
fieldshow export-midi show.json -o score.mid
fieldshow export-om show.json -o show.om
fieldshow serve --show show.json --host 0.0.0.0 --port 8876
```

`show.om` opens in OpenMarch. `score.musicxml` opens in MuseScore or any MusicXML editor. The serve page is the integrated view: dots, parts, and the uniform and flag notes together.

## Pictures

If the user attaches a field photo or a chart image, call `import-image` and also describe what you see in the set names. This program stores the picture and draws it under the dots. It does not trace dots out of the photo. You place the shapes.
