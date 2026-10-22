# Pending handoff, 2026-10-22

T-0005 is implemented on branch `build/t0005-part-pdfs` (pushed to origin; no PR, not merged to main). Implemented headless by Grok Build on nimo in a worktree under `tmp/`, then verified independently.

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
docker run --rm -v "$PWD:/work" -w /work -e HOME=/tmp --user "$(id -u):$(id -g)" fieldshow:t0005 \
  sh -c 'python -m venv /tmp/v --system-site-packages && . /tmp/v/bin/activate && pip install -q --no-cache-dir -e ".[dev]" && pytest'
```

`fieldshow:t0005` is 227MB on disk, 200MB content (`docker images` on nimo, image `3237f51ba193`, Round 3). Earlier notes said 278MB; that was a different measurement and is wrong for this image. `python:3.12-slim` is 51MB. LilyPond 2.24.4 plus the libraries apt pulls in for it (Guile, Ghostscript, URW fonts, Cairo, Pango) are about 110MB installed. The eval image that contained both MuseScore and LilyPond was 589MB and is not what we deploy.

## Decision

OQ-0001 is closed. LilyPond engraves the parts. See `docs/adr/0004-lilypond-part-pdfs.md` and `docs/ops/AUTONOMOUS-DECISIONS-2026-10-22.md`.

On Gate Fanfare, musicxml2ly kept every pitch, rhythm, clef, part name, key, time signature, and the 132 tempo. The source has no dynamics, articulations, or transposition label, and neither engraver invented any. MuseScore 3.2.3 was faster (about 0.12s versus 1.3s for one part) but dropped the staff name on a one-line part and stacked all eleven tempo marks on the flute of the full score.

## Parked

- OQ-0002 field photo tracing
- OQ-0003 pit, guard, and props
- OQ-0004 step-size and collision warnings
- OQ-0005 no login on the LAN page. Unchanged. No new port.
- Battery parts (snare, bass drum) are engraved on a pitched treble staff with the key signature, because the arranger stores them as pitch tokens. A percussion clef / one-line staff is a follow-up (OQ-0003 territory).
- MuseScore stays out of the image. If a later chart shows a musicxml2ly octave or rhythm loss, re-run the ADR 0004 comparison.

## Verification

Host: 16 passed, 2 skipped (engraving tests skip without LilyPond). Image `fieldshow:t0005`: 18 passed.

Mutation proof (one at a time, restored after each):

| Mutation | Result |
| --- | --- |
| Engrave loop only does `SECTION_ORDER[:1]` | red: `test_build_writes_one_real_pdf_per_part`, `test_page_links_each_part_pdf` |
| PDF written as empty bytes | red: same two tests |
| Missing-engraver guard removed (`if False:`) | red: `test_missing_engraver_builds_and_page_marks_parts_unavailable` |
| Missing engraver raises instead of recovering | red: `test_missing_engraver_builds_and_page_marks_parts_unavailable` |

## CI

The repo has no `.github/workflows/`, so no CI runs on any push (`build/**` or `main`). Nothing was added; the tests above are the gate.

The container still serves the sample intent until a built show is mounted. Paper links stay unavailable until `fieldshow build` has written `parts/` beside that file. An intent edit that changes the music clears the links until the next build.

## Deploy

Sysadmin redeploys on host `maximum` per `docs/ops/deploy-maximum.md`: rsync the tree, then `docker compose up -d --build`. The engraver is in the image (`Dockerfile` installs `lilypond`). Expect the image to grow by the LilyPond stack described above. Do not rely on a host install of LilyPond. `QT_QPA_PLATFORM` is not required. LilyPond is not a Qt program. PDFs are produced by `fieldshow build`, not by the server: to serve linked parts on maximum, run the build (inside the image is fine) and bind-mount the directory holding `show.json` and its `parts/` (e.g. at `/data`, `FIELDSHOW_SHOW=/data/show.json`). Mounting only the JSON file leaves the parts marked unavailable.

## Round 2

Tester and Reviewer both FAILed `3c9fca0`: the parts engraved, and the tests did not lock the behavior. Pushed to `build/t0005-part-pdfs` with a normal push. No PR, no merge. No CI workflow was added.

### What changed

- **B1.** The engraved-build test runs `pdftotext` on each `parts/<section>.pdf`. The text must contain that section's `PART_NAMES` value and must not contain another part's name unless one name is a substring of the other. Flute text differs from tuba text, trumpet from snare, and the eleven PDF bodies are not identical. `GET /api/part-pdf/{section}` returns the bytes of `parts/<section>.pdf`. The image installs `poppler-utils` for `pdftotext`.
- **B2 / RB1.** `tests/test_part_pdfs.py::test_export_parts_start_at_offset_zero` exports the arranged Gate Fanfare with no engraver. Eleven parts, two `<measure>` elements each, first note at offset 0, and no `print-object="no"`. That is the `repro_offset.py` failure on main (`Score.append`). `export_midi` uses the same score, so MIDI parts start together too (`docs/ARCHITECTURE.md`).
- **B3.** The fake `lilypond` writes a `%PDF` at the `-o` prefix plus `.pdf`, then exits 4. The build still exits 0, stderr contains `lilypond exited 4`, `part_pdfs` is null, and `parts/` has no PDF.
- **S1.** Each failed part stores a short `part_errors[section]` (`lilypond exited 4`, `timed out`). The page row is only that reason. The stderr tail stays on stderr and in `engrave_error`, and it is not in the HTML (`/tmp/` and `fieldshow-engrave-` are absent; each paper `<li>` is under 200 characters). A missing engraver is one banner line plus `unavailable` on each row, not `unavailable: PDF parts unavailable`.
- **S2.** `engrave_parts` deletes every existing `parts/<section>.pdf` before engraving, including the missing-engraver return. A pre-seeded `%PDF` is gone after a missing-engraver build and after a failing engraver, and `create_app` on that JSON returns 404. The old per-part `dest.unlink()` in the except branch was dead (the PDF is copied only after success) and is removed. The live mutant is "stale clear removed".
- **S3 / RB2.** The route serves only `<show_dir>/parts/<section>.pdf` for a section in `SECTION_ORDER`, and only when `part_pdfs[section]` is exactly that relative marker. The path is computed, resolved, and must be `is_relative_to` the resolved `parts/` directory and a real file. `ValueError` and `OSError` are 404. Covered, all 404 and never the foreign bytes: `../show.json`, `%2e%2e%2fshow.json`, a symlink out of `parts/`, JSON values `show.json`, `../x`, `/etc/passwd`, `notes.txt`, and a NUL, including when a real part PDF is also on disk. A planted `parts/not-a-part.pdf` is 404. A good marker still returns that file.
- **Q9.** `POST /api/intent` with `tempo` clears the links and the route is 404. A design-only intent keeps the links.
- **Timeout.** Both engraver subprocesses use `start_new_session=True` and `Popen.communicate(timeout=...)`. On `TimeoutExpired`, `os.killpg(pid, SIGKILL)` kills the grandchild. `FIELDSHOW_ENGRAVE_TIMEOUT` is seconds, default 120. The fake `lilypond` backgrounds `sleep 300`, records the pid, and sleeps. With the timeout at 2s the build exits 0, the short reason is `timed out`, and each child pid is gone (`ProcessLookupError` or a reaped zombie).
- **Evidence.** `docs/adr/0004-evidence/` holds the eval Dockerfile, `render.sh`, the out2 commands, the small input MusicXML, pdfinfo and pdftotext logs, and `contact-sheet.png` (MuseScore vs LilyPond, trumpet and simultaneous full score, MuseScore page 2). About 384 KB. ADR 0004 links it and records that the MuseScore lean was the CEO's daily product touch (the ticket brief), and that these pages overrode it.
- **Deploy.** `docs/ops/deploy-maximum.md` mounts the whole show directory through a `compose.override.yaml` on maximum (`/home/mark/fieldshow-data:/data`, `FIELDSHOW_SHOW=/data/show.json`), builds with `docker compose run --rm --user ... fieldshow fieldshow build /data/intent.json -o /data/show.json`, and checks `/api/part-pdf/trumpet` for `200 application/pdf`. The rsync now excludes `tmp/` (worktrees) and the override. That compose run flow was smoke-tested on nimo with a throwaway project (no ports published): 11 PDFs.
- **AGENTS.md** names `musicxml2ly` and `FIELDSHOW_MUSICXML2LY`.

### Verification

Final run at `0585cf6`. The commit after it changes only this file, so `src/`, `tests/` and `Dockerfile` are identical at the pushed tip.

Host `.venv` (engraving tests skip): `22 passed, 2 skipped, 1 warning in 24.27s`.

Docker build `docker build -t fieldshow:t0005 .`, exit 0:

```
#13 naming to docker.io/library/fieldshow:t0005 done
#13 unpacking to docker.io/library/fieldshow:t0005 1.5s done
#13 DONE 7.1s
```

Image `a713319b9a54`, 227 MB. In-image pytest, worktree mounted read-only, `--user "$(id -u):$(id -g)"`, `PYTHONPATH=/work/src`, pytest and httpx from a throwaway venv under `/tmp`:

```
24 passed, 1 warning in 39.49s
```

The warning is the existing Starlette note about httpx. No root-owned files were left in the worktree.

Spot mutants, each in a scratch copy run in the image at `0585cf6` (clean copy `24 passed`):

- Route serves `flute.pdf` for every section: `2 failed` (`test_page_links_each_part_pdf`, `test_part_pdf_route_rejects_null_tamper_and_escape`: `b'%flute-real' == b'%baritone-good'`).
- `SECTION_ORDER` check and `is_relative_to(parts/)` removed: `1 failed` (`test_part_pdf_route_rejects_null_tamper_and_escape`, line 365).
- `os.killpg` replaced by `proc.kill()`: `1 failed` (`test_engrave_timeout_kills_grandchild`: "build hung; the engraver timeout did not stop the part").

### Mutants

`tmp/mutants/run_r2.py` (not committed; `tmp/` is gitignored) applied each patch in a fresh tree and ran pytest in `fieldshow:t0005` as the host uid. The table has 25 rows. Counting every alias name it is 35 mutants, which is what the runner printed; D3 = M7 and Q3 = M11 are the same patch, so there are 23 distinct patches: 21 CAUGHT, 2 EQUIVALENT, 0 survived (re-run by DevBot at `2ca2278`). Aliases that share a patch share the failing tests. M3 is EQUIVALENT (the stored string is not opened). M6 is not observable through the app rather than strictly equivalent: the removed unlink also covered `dest.write_bytes()` failing partway (for example ENOSPC), which can leave a truncated `parts/<s>.pdf` until the next build, but the marker is null so the route still 404s. The live containment check is `is_relative_to(parts/)`. The live stale-file check is `_clear_part_pdfs`, caught as Q6 / R-stale.

| Mutant | Result | Failing tests |
| --- | --- | --- |
| D1 engrave loop `SECTION_ORDER[:1]` | CAUGHT | `test_build_writes_one_real_pdf_per_part`, `test_page_links_each_part_pdf`, `test_lilypond_exit_status_discards_the_pdf_it_wrote`, `test_failed_engrave_page_shows_only_the_short_reason`, `test_engrave_timeout_kills_grandchild`, `test_engraver_path_with_a_space_still_writes_pdfs` |
| D2 PDF written as empty bytes | CAUGHT | `test_build_writes_one_real_pdf_per_part`, `test_page_links_each_part_pdf`, `test_engraver_path_with_a_space_still_writes_pdfs` |
| D3 missing-engraver guard removed (`if False`) | CAUGHT | `test_missing_engraver_builds_and_page_marks_parts_unavailable` |
| D4 missing engraver raises | CAUGHT | `test_missing_engraver_builds_and_page_marks_parts_unavailable` |
| Q1 set-but-missing engraver falls through to `PATH` | CAUGHT | `test_missing_engraver_builds_and_page_marks_parts_unavailable` |
| Q2 route serves flute for every section | CAUGHT | `test_page_links_each_part_pdf`, `test_part_pdf_route_rejects_null_tamper_and_escape` |
| Q3 content-type `application/octet-stream` | CAUGHT | `test_page_links_each_part_pdf`, `test_part_pdf_route_rejects_null_tamper_and_escape` |
| Q4 / M5 / R-M5 `Score.append` | CAUGHT | `test_export_parts_start_at_offset_zero` |
| Q5 / M8 ignore lilypond return code | CAUGHT | `test_lilypond_exit_status_discards_the_pdf_it_wrote`, `test_failed_engrave_page_shows_only_the_short_reason` |
| Q6 / R-stale stale-PDF clearing removed | CAUGHT | `test_lilypond_exit_status_discards_the_pdf_it_wrote`, `test_missing_engraver_builds_and_page_marks_parts_unavailable` |
| Q7 every part engraves flute's notes | CAUGHT | `test_build_writes_one_real_pdf_per_part` |
| Q8 / M4 ignore JSON null and serve a file on disk | CAUGHT | `test_part_pdf_route_rejects_null_tamper_and_escape`, `test_music_intent_hides_pdfs_and_design_intent_keeps_them` |
| Q9 / M10 / R-M10 intent does not clear `part_pdfs` | CAUGHT | `test_music_intent_hides_pdfs_and_design_intent_keeps_them` |
| Q10 page links every part when unavailable | CAUGHT | `test_missing_engraver_builds_and_page_marks_parts_unavailable`, `test_failed_engrave_page_shows_only_the_short_reason`, `test_engrave_timeout_kills_grandchild`, `test_music_intent_hides_pdfs_and_design_intent_keeps_them` |
| Q11 per-part failure does not set `engrave_error` | CAUGHT | `test_lilypond_exit_status_discards_the_pdf_it_wrote`, `test_engrave_timeout_kills_grandchild` |
| Q12 failure still records `part_pdfs` | CAUGHT | `test_lilypond_exit_status_discards_the_pdf_it_wrote`, `test_failed_engrave_page_shows_only_the_short_reason`, `test_engrave_timeout_kills_grandchild` |
| Q13 part name dropped | CAUGHT | `test_build_writes_one_real_pdf_per_part`, `test_musicxml_and_midi_round_trip` |
| M1 / R-M1 drop timeout and `killpg` | CAUGHT | `test_engrave_timeout_kills_grandchild` |
| M2 / R-M2 `" ".join(argv)` and `shell=True` | CAUGHT | `test_engraver_path_with_a_space_still_writes_pdfs` |
| M3 remove only the old `..` / absolute scan | EQUIVALENT | Stored `part_pdfs` strings are not opened. The file name is `parts/<section>.pdf`. Containment is `resolve` plus `is_relative_to(parts/)`, caught by M3b. |
| M3b / R-M3b remove `is_relative_to(parts/)` | CAUGHT | `test_part_pdf_route_rejects_null_tamper_and_escape` |
| M6 skip `dest.unlink()` | NOT OBSERVABLE | That unlink is gone. Stale files are cleared up front; removing that call is Q6 / R-stale. |
| M7 missing-engraver guard `if False` | CAUGHT | same as D3: `test_missing_engraver_builds_and_page_marks_parts_unavailable` |
| M9 drop `section not in SECTION_ORDER` | CAUGHT | `test_part_pdf_route_rejects_null_tamper_and_escape` |
| M11 `application/octet-stream` | CAUGHT | same as Q3 |

### Parked

- `HEAD` on `/api/part-pdf/{section}` stays 405. Not changed.
- Arranger range and transposition, filed separately by PM: transposed parts carry the concert key signature, tenor sax is in bass clef at the wrong octave, alto sax A3 is below range, mellophone reaches F6, battery is on a pitched staff.
- No CI workflow. PM follow-up. Nothing under `.github/` was added.
- `field_image` can still be an arbitrary file read through `apply_intent` and `GET /api/field-image`. Pre-existing. PM files it separately. Not touched here.
