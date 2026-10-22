# Pending handoff, 2026-10-22

T-0005 is implemented on `build/t0005-part-pdfs` in this worktree. Nothing was pushed.

## What shipped

`fieldshow build` arranges, charts, and writes one LilyPond PDF per section next to the show JSON (`parts/trumpet.pdf` and the other names in `SECTION_ORDER`). The show records `part_pdfs` (relative path or null) and `engrave_error`. The page links `GET /api/part-pdf/{section}` when a file exists and marks the part unavailable, with the reason, when it does not. The route returns 404 for a missing part. The server does not run LilyPond.

A missing engraver prints `PDF parts unavailable: LilyPond not found (set FIELDSHOW_ENGRAVER)` on stderr, stores null paths, and exits 0. A non-zero `lilypond` or `musicxml2ly` exit does the same for that part. Set `FIELDSHOW_ENGRAVER` or `FIELDSHOW_LILYPOND` to the `lilypond` binary, and `FIELDSHOW_MUSICXML2LY` to the converter. Otherwise both come from `PATH`.

Parts are inserted at offset 0 in the MusicXML. The evaluation export had used `Score.append`, which laid the parts end to end and padded twenty hidden measures. The build does not engrave those.

## How to run

Host, without LilyPond. The two engraving tests skip. The failure tests run.

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
pytest
fieldshow build examples/fanfare.json -o /tmp/show.json
```

Image. This is the command the skip message prints. It ran green here: 18 passed.

```bash
docker build -t fieldshow:t0005 .
docker run --rm -v "$PWD:/work" -w /work -e HOME=/tmp fieldshow:t0005 \
  sh -c 'pip install --no-cache-dir -e ".[dev]" && pytest'
```

`fieldshow:t0005` is 236MB (`docker images`). `python:3.12-slim` is 51MB. LilyPond 2.24.4 plus the libraries apt pulls in for it (Guile, Ghostscript, URW fonts, Cairo, Pango) are about 110MB installed. The eval image that contained both MuseScore and LilyPond was 589MB and is not what we deploy.

## Decision

OQ-0001 is closed. LilyPond engraves the parts. See `docs/adr/0004-lilypond-part-pdfs.md` and `docs/ops/AUTONOMOUS-DECISIONS-2026-10-22.md`.

On Gate Fanfare, musicxml2ly kept every pitch, rhythm, clef, part name, key, time signature, and the 132 tempo. The source has no dynamics, articulations, or transposition label, and neither engraver invented any. MuseScore 3.2.3 was faster (about 0.12s versus 1.3s for one part) but dropped the staff name on a one-line part and stacked all eleven tempo marks on the flute of the full score.

## Parked

- OQ-0002 field photo tracing
- OQ-0003 pit, guard, and props
- OQ-0004 step-size and collision warnings
- OQ-0005 no login on the LAN page. Unchanged. No new port.

The container still serves the sample intent until a built show is mounted. Paper links stay unavailable until `fieldshow build` has written `parts/` beside that file. An intent edit that changes the music clears the links until the next build.

## Deploy

Sysadmin redeploys on host `maximum` per `docs/ops/deploy-maximum.md`: rsync the tree, then `docker compose up -d --build`. The engraver is in the image (`Dockerfile` installs `lilypond`). Expect the image to grow by the LilyPond stack described above. Do not rely on a host install of LilyPond. `QT_QPA_PLATFORM` is not required. LilyPond is not a Qt program.
