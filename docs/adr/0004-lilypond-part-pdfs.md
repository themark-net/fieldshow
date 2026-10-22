# ADR 0004: LilyPond engraves the part PDFs

- Status: Accepted
- Date: 2026-10-22
- Supersedes: the "leave engraving out of the container" note in ADR 0002, for paper parts only

## Context

OQ-0001 asked whether MuseScore or LilyPond should engrave the paper parts. `fieldshow build` already writes MusicXML through music21. The deployed image is `python:3.12-slim` (Debian trixie). Both tools install from apt: `musescore3` 3.2.3 and `lilypond` 2.24.4 (`musicxml2ly` ships in that package).

The comparison used Gate Fanfare (`examples/fanfare.json`), arranged and exported with `fieldshow build` and `fieldshow export-musicxml` on 2026-10-22. The source MusicXML is 11 parts, key Bb (two flats), 4/4, a quarter-note metronome of 132 on every part, and no dynamics, articulations, or `<transpose>` element. Written pitches are already transposed. `Score.append` had also parked the parts end to end, so that export contained 20 hidden measure-rests (`print-object="no"`) after the two sounding bars. A second export put every part at offset 0 (two bars, tempo still on every part) and a third was trumpet alone. Renders ran in `fieldshow-engrave-eval:t0005` with `QT_QPA_PLATFORM=offscreen`, `mscore3 -o out.pdf in.musicxml`, and `musicxml2ly` then `lilypond --pdf`. Pages and text came from `pdfinfo` and `pdftotext`. Pictures came from `pdftoppm -png -r 100`.

Pitches were checked against the arranged parts, and for LilyPond also against the generated `.ly` (the `\relative` spelling resolves to the same octaves).

| Score | MuseScore 3.2.3 | LilyPond 2.24.4 |
| --- | --- | --- |
| Full export, including 20 hidden measure-rests | 0.439 s, 3 pages, PDF 36,919 bytes, PNG 94,325 bytes. Notes match. Part names present. Hidden rests are printed as whole rests. | 1.457 s, 1 page, PDF 54,291 bytes, PNG 64,062 bytes. Notes, names, clefs, key, time, and one tempo match. Hidden rests become spacers (`s1*20`), not rest glyphs. |
| Trumpet, same padded export | 0.126 s, 1 page, PDF 28,488 bytes, PNG 17,860 bytes. Pitches C5 E5 G5 C6 B5 A5 G5 F5, two flats, 4/4, quarter = 132. Staff name omitted. Rests printed. | 1.231 s, 1 page, PDF 49,607 bytes, PNG 23,429 bytes. Same pitches, key, time, and tempo. Staff name "Trumpet". |
| Full score, parts simultaneous, tempo on every part | 0.353 s, 2 pages, PDF 33,039 bytes, PNG 69,165 bytes. Page 1 is the title only. Page 2 has the notes and every part name, and stacks all 11 tempo marks on the flute. | 1.373 s, 1 page, PDF 52,819 bytes, PNG 62,661 bytes. All 11 parts readable. One tempo. Names, clefs, key, 4/4, and the bass-drum rests match. |
| Trumpet, two sounding bars only | 0.124 s, 1 page, PDF 27,932 bytes, PNG 15,514 bytes. Pitches, key, time, and tempo match. Staff name omitted. | 1.251 s, 1 page, PDF 49,423 bytes, PNG 23,337 bytes. Same music. Staff name "Trumpet". |

PNG delta on the clean trumpet page: LilyPond is 7,823 bytes larger (+50%). On the simultaneous full score the MuseScore PNGs are larger by 6,504 bytes because of the blank title page. MuseScore is about 4 to 10 times faster. Neither tool invented dynamics, articulations, or a transposition label such as "in Bb". The source has none.

## Decision

LilyPond engraves the part PDFs. `fieldshow build` writes one MusicXML staff per section and runs `musicxml2ly` then `lilypond`. The binaries are `FIELDSHOW_ENGRAVER` or `FIELDSHOW_LILYPOND`, then `musicxml2ly` from `FIELDSHOW_MUSICXML2LY` or `PATH`. The image installs `lilypond`.

musicxml2ly was not lossy on this chart. Every pitch, rhythm, clef, part name, key, time signature, and tempo survived the `.ly` file. MuseScore's pages were the ones that dropped information: the one-staff part has no name, and the full score piles a tempo mark from every part onto the flute.

## Rejected alternatives

- MuseScore 3, which was the lean before the render. It is faster and imports MusicXML without a relative-octave step. On the file we actually write it hides the part name and, when every part carries a metronome, covers the top staff with eleven tempo marks. A later chart with a wide leap could still expose a musicxml2ly octave bug. This fanfare did not.
- Ship both and pick at runtime. Two engraving stacks in the image, and the page would need two failure stories.
- Keep MusicXML only and engrave by hand. That was ADR 0002, before paper parts were in the build.

## Consequences

`fieldshow build` writes `parts/<section>.pdf` beside the show JSON and records `part_pdfs` plus `engrave_error`. A missing or failing engraver prints the reason on stderr, stores null paths, and still exits 0. The page links `/api/part-pdf/{section}` only for a file that exists. Parts are inserted at offset 0 before export, so the hidden measure-rests in the evaluation file are not what the build engraves. The image grows by the LilyPond packages. Sysadmin redeploys on `maximum` with the image rebuild in `docs/ops/deploy-maximum.md`.
