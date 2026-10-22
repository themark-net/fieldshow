# Handoff: #3 field_image path restriction, 2026-10-22

Branch `build/3-field-image`, off `a803da2`, which is now `main` (T-0005 fast-forwarded). Pushed to origin, no PR, not merged to main.

## Problem

`field_image` was a free-form path settable through `POST /api/intent`. `GET /api/field-image` then served whatever file it named, so a LAN client could read any file the server could open.

## What changed

- `field_image` is now `null` or the marker `images/<name>.<ext>`: the name is 1 to 64 characters of `[A-Za-z0-9_-]` and starts with a letter or digit, and the extension is png, jpg, jpeg, webp or gif (`model.FIELD_IMAGE_RULE`, `field_image_ok`). Absolute paths, `..`, `./`, `//`, `%2e` and NUL never match.
- Intent time: `apply_intent` raises on a bad marker, and `/api/intent` maps ValueError to 422. The handler also returns 422 if the marker names no regular file inside `images/`. The show is unchanged on 422.
- Serve time: `_field_image_file` checks the marker again. For the upload temp dir and the show dir it resolves `images/`, skips the root if `images/` resolves outside it, resolves the file, and requires `is_relative_to(images)` and `is_file()`. ValueError, OSError and RuntimeError (Python 3.12 symlink loop) become 404, as in the part-PDF route.
- Uploads (`POST /api/image`) still go to the temp upload dir, stored as `images/field.<ext>`. The client filename is ignored, and nothing is written into the show dir.
- `fieldshow import-image` copies to `<show json dir>/images/field.<ext>` and stores the marker. The `--assets` flag is gone.
- The bad `FIELDSHOW_ENGRAVE_TIMEOUT` test now covers abc, 0, -1, inf and nan. The parser already rejected all of them (`0 < value < inf`), so it is unchanged.
- The decision is logged in `docs/ops/AUTONOMOUS-DECISIONS-2026-10-22.md`.

## DoD → tests (`tests/test_field_image.py` unless noted)

| Item | Test |
|---|---|
| Reject at intent, 4xx, intent unchanged (`../`, absolute, symlink-out, NUL, %2e, show.json, missing) | `test_intent_rejects_field_image_outside_images[*]` (10 cases) |
| Serve-time 404 from a tampered show JSON (same 10 values) | `test_serve_404s_a_tampered_field_image_in_the_show_json[*]` |
| `images/` symlinked outside the show | `test_serve_404s_when_images_dir_points_outside_the_show` |
| Symlink loop, unreadable `images/` → 404, not 500 | `test_serve_404s_on_a_symlink_loop_or_unreadable_images_dir` (the chmod half skips as root) |
| Non-canonical markers that resolve to the real image | `test_non_canonical_markers_are_refused_even_if_they_land_on_the_real_image[*]` |
| Legit image served with correct bytes; set and clear | `test_legit_field_image_is_served_and_can_be_set_and_cleared` |
| Upload stored as a marker; traversal filename ignored | `test_upload_is_stored_as_a_marker_and_served` |
| CLI import writes the marker | `tests/test_model.py` import test |
| Timeout 0, -1, inf, nan, abc | `tests/test_part_pdfs.py::test_bad_engrave_timeout_fails_the_build_and_keeps_old_pdfs[*]` |

## Mutants

Each mutant ran in a scratch copy, in `fieldshow:t0005` as the host uid. The tree was restored after every run (scratch only).

All CAUGHT. CLEAN ran green: 62 passed in the image after the non-canonical test was added. That test was added because S-regex survived the first run, at 58/58.

| Mutant | Change | Result | Red line |
|---|---|---|---|
| I-both (intent guard removed) | drop the `apply_intent` raise; handler check `and False` | 14 failed | `test_intent_rejects_field_image_outside_images[/etc/passwd]` … `test_field_image.py:62: AssertionError: {"title":"Gate Fanfare"}` (422 expected) |
| I-handler | handler file check only | 2 failed | `test_intent_rejects_…[images/out.png]`, `[images/missing.png]` |
| S-serve (serve guard removed) | route back to raw `Path(path).is_file()` | 16 failed | `test_field_image.py:66: assert 404 == 200` plus the tampered serve cases |
| S-contain | drop `is_relative_to(images)` | 2 failed | `test_serve_404s_a_tampered_field_image_in_the_show_json[images/out.png]` |
| S-root | drop the images-inside-root check | 1 failed | `test_serve_404s_when_images_dir_points_outside_the_show` `:93: assert 200 == 404` |
| S-regex | drop `field_image_ok` at serve | 4 failed | `test_non_canonical_markers_…[ABS_LEGIT]` `:147: assert 200 == 404` |
| S-except | except → ZeroDivisionError | 1 failed | `test_serve_404s_on_a_symlink_loop_…` `:126: assert 500 == 404` |
| T-nan | timeout parser `if value <= 0:` | 3 failed | `test_bad_engrave_timeout_…[inf]`, `[nan]` |

Scripts: `tmp/mutants/run_3.sh` and `run_3b.sh` (gitignored). Logs: `/tmp/fs-3-mutants.log` and `/tmp/fs-3-mutants-b.log` on nimo.

## Reviewer nits folded in (T-0005)

- N2: Python 3.13 and later do not raise on a symlink loop in `Path.resolve()` (non-strict). The path comes back unresolved and `is_file()` is False, so the result is 404 either way. Python 3.12, the image's interpreter, raises RuntimeError, so the RuntimeError catch stays in both the part-PDF and field-image guards.
- N3: T-0005 mutant M6 is relabelled "not observable", not "equivalent". The summary in `docs/PENDING-HANDOFF.md` now reads 21 CAUGHT, 1 EQUIVALENT (M3), 1 NOT OBSERVABLE (M6).

## Parked

- An upload whose bytes fail `import_image` (bad extension or ValueError) still returns 500. This is pre-existing and was not in #3's scope.
- Merge and redeploy belong to the parent. The Tester and Reviewer gates are pending. T-0005 is on main at `a803da2`, which is this branch's base.

## Evidence

Run on nimo at code commit `d530bc8`. The commit after it changes docs only.

- `docker build -t fieldshow:t0005 .`: exit 0, `#13 DONE 7.1s`
- In-image pytest (`fieldshow:t0005`, Python 3.12, host uid, `:ro` mount): `62 passed, 1 warning in 41.82s`
- Host pytest (Python 3.14): `60 passed, 2 skipped, 1 warning in 26.31s`. The 2 skips are the LilyPond engraving tests; the chmod half of the loop test runs here.
- Files not owned by the host uid in the worktree: 0
