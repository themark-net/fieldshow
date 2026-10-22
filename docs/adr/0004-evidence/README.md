# ADR 0004 render evidence

This is the 2026-10-22 comparison that picked LilyPond. `contact-sheet.png` is MuseScore against LilyPond for the clean trumpet part and the simultaneous full score (MuseScore page 2, which is where the notes are). The sheets are cropped to the music and downscaled. PDFs and the original page PNGs are not committed.

MuseScore was the lean before these pages. That lean was the CEO's daily product touch (the ticket brief). The pages overrode it: the trumpet staff has no name in MuseScore, and the full score stacks a tempo mark from every part on the flute. LilyPond keeps the staff name and one tempo.

## Eval image

`Dockerfile` builds `fieldshow-engrave-eval:t0005` (MuseScore 3, LilyPond, poppler). It is not the deploy image. The deploy image is the repo root `Dockerfile`, which installs LilyPond only.

```bash
docker build -t fieldshow-engrave-eval:t0005 -f docs/adr/0004-evidence/Dockerfile .
docker run --rm -v "$PWD/docs/adr/0004-evidence:/work" -w /work \
  -e HOME=/tmp --user "$(id -u):$(id -g)" \
  fieldshow-engrave-eval:t0005 sh render.sh
```

`render.sh` writes `out/full` from `in/fanfare.musicxml` (parts laid end to end, with the hidden rests) and `out/trumpet` from `in/trumpet.musicxml`. Do not commit `out/`.

## Commands for the contact sheet (`out2`)

Same tools, the two clean inputs. `in/trumpet-clean.musicxml` is the trumpet with two sounding bars. `in/fanfare-simultaneous.musicxml` puts every part at offset 0 with a tempo on each part. `in/fanfare-one-tempo.musicxml` is the full score with one tempo mark, kept so that export can be re-rendered. `logs/trumpet` and `logs/simultaneous` are the pdfinfo, pdftotext, timings, and short tool logs from that run.

```bash
docker run --rm -v "$PWD/docs/adr/0004-evidence:/work" -w /work \
  -e HOME=/tmp -e QT_QPA_PLATFORM=offscreen --user "$(id -u):$(id -g)" \
  fieldshow-engrave-eval:t0005 sh -c '
set -u
render() {
  name="$1"; src="$2"; dest="/work/out2/$name"
  mkdir -p "$dest"
  mscore3 -o "$dest/musescore.pdf" "$src" >"$dest/musescore.log" 2>&1
  ( cd "$dest" && musicxml2ly -o score.ly "$src" >lilypond-convert.log 2>&1 \
      && lilypond --pdf -o lilypond score.ly >lilypond.log 2>&1 )
  for eng in musescore lilypond; do
    pdfinfo "$dest/$eng.pdf" >"$dest/$eng.info"
    pdftotext -layout "$dest/$eng.pdf" "$dest/$eng.txt"
    pdftoppm -png -r 100 "$dest/$eng.pdf" "$dest/$eng"
  done
}
render trumpet /work/in/trumpet-clean.musicxml
render simultaneous /work/in/fanfare-simultaneous.musicxml
'
```

Do not commit `out2/` either. The picture in this directory is the contact sheet.

The LilyPond footer in `logs/*/lilypond.txt` is stored with an ASCII hyphen. The PDF credit uses a dash glyph; the text here does not, so the file stays ASCII.
