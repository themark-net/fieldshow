#!/bin/sh
# Render the exported fanfare with MuseScore 3 and LilyPond. Evidence only.
set -u
INDIR=/work/in
OUTDIR=/work/out
mkdir -p "$OUTDIR"

seconds() {
  python3 -c 'import time,sys; print(f"{time.time():.3f}")'
}

render_one() {
  name="$1"
  src="$2"
  dest="$OUTDIR/$name"
  mkdir -p "$dest"
  echo "=== $name ==="

  t0=$(seconds)
  mscore3 -o "$dest/musescore.pdf" "$src" >"$dest/musescore.log" 2>&1
  echo "musescore_exit=$?" | tee -a "$dest/musescore.log"
  t1=$(seconds)
  python3 -c "print(round($t1 - $t0, 3))" | tee "$dest/musescore.seconds"

  t0=$(seconds)
  (
    cd "$dest" || exit 1
    musicxml2ly -o score.ly "$src" >lilypond-convert.log 2>&1
    echo "musicxml2ly_exit=$?" | tee -a lilypond-convert.log
    if grep -q "musicxml2ly_exit=0" lilypond-convert.log; then
      lilypond --pdf -o lilypond score.ly >lilypond.log 2>&1
      echo "lilypond_exit=$?" | tee -a lilypond.log
    else
      echo "lilypond_skipped" | tee lilypond.log
    fi
  )
  t1=$(seconds)
  python3 -c "print(round($t1 - $t0, 3))" | tee "$dest/lilypond.seconds"

  for eng in musescore lilypond; do
    pdf="$dest/$eng.pdf"
    if [ -f "$pdf" ]; then
      pdfinfo "$pdf" >"$dest/$eng.info" 2>"$dest/$eng.info.err" || true
      pdftotext -layout "$pdf" "$dest/$eng.txt" 2>>"$dest/$eng.info.err" || true
      pdftoppm -png -r 100 "$pdf" "$dest/$eng" 2>>"$dest/$eng.info.err" || true
      ls -la "$pdf" "$dest/$eng"*.png >"$dest/$eng.sizes" 2>/dev/null || true
    else
      echo "missing $pdf" | tee "$dest/$eng.sizes"
    fi
  done
}

render_one full "$INDIR/fanfare.musicxml"
render_one trumpet "$INDIR/trumpet.musicxml"
echo DONE
