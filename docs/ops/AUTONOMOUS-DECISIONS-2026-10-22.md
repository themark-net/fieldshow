# Autonomous decisions, 2026-10-22

The session picked a reversible default from the render evidence, wrote it down, and kept going.

| Choice | Alternatives | Why |
| --- | --- | --- |
| LilyPond engraves part PDFs (ADR 0004) | MuseScore 3, or leave MusicXML for a person to engrave | On Gate Fanfare, musicxml2ly kept every pitch, rhythm, clef, name, key, time, and tempo. MuseScore dropped the one-staff part name and stacked eleven tempo marks on the flute. |
| #3: `field_image` is only `images/<name>.<png|jpg|jpeg|webp|gif>` (one segment, no dots or `%`), resolved inside `<show_dir>/images/` or the server's own temp upload dir; uploads stay in that temp dir and `import-image` copies to `<output dir>/images/` (its `--assets` flag is gone) | Any file inside the show dir; a bare-name allowlist with no folder | The narrowest rule that still serves a picture beside the show. A LAN client can name only images under one folder, never `show.json` or `parts/`, and an upload never writes into the operator's show dir (the container runs as root). |
| #3 r2: non-image upload returns 415 (not 422), and "readable" is checked by opening the file, not `os.access` | 422 like intent; `os.access(R_OK)`; keep the 500 parked | 415 names the cause (wrong media type). `os.access` is always true for root, and the container runs as root |
