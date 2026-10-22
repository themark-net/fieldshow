# Handoff: #3 field_image path restriction, 2026-10-22

Branch `build/3-field-image`, off `a803da2`, which is now `main` (T-0005 fast-forwarded). Pushed to origin, no PR, not merged to main.

## Problem

`field_image` was a free-form path settable through `POST /api/intent`. `GET /api/field-image` then served whatever file it named, so a LAN client could read any file the server could open.

## What changed

- `field_image` is now `null` or the marker `images/<name>.<ext>`: the name is 1 to 64 characters of `[A-Za-z0-9_-]` and starts with a letter or digit, and the extension is png, jpg, jpeg, webp or gif (`model.FIELD_IMAGE_RULE`, `field_image_ok`). The regex is `re.IGNORECASE | re.ASCII`; IGNORECASE alone (round 1) also matched the Kelvin sign, dotless i and long s, so `images/\u212a.png` and `imageſ/` passed. Absolute paths, `..`, `./`, `//`, `%2e` and NUL never match.
- Intent time: `apply_intent` raises on a bad marker, and `/api/intent` maps ValueError to 422. The handler also returns 422 if the marker names no regular file inside `images/`. The show is unchanged on 422.
- Serve time: `_field_image_file` checks the marker again. For the upload temp dir and the show dir it resolves `images/`, skips the root if `images/` resolves outside it, resolves the file, and requires `is_relative_to(images)`, `is_file()`, and that the file opens for reading. An unreadable file is 422 at intent and 404 at serve. In round 1 it was accepted, then the response died mid-body with a PermissionError. ValueError, OSError and RuntimeError (Python 3.12 symlink loop) become 404, as in the part-PDF route.
- Uploads (`POST /api/image`) still go to the temp upload dir, stored as `images/field.<ext>`. The client filename is ignored, and nothing is written into the show dir. A non-image suffix is now 415 (it was a 500), the show is unchanged, and the `upload.<suffix>` scratch file is deleted either way.
- `fieldshow import-image` copies to `<show json dir>/images/field.<ext>` and stores the marker. The `--assets` flag is gone, and so is the `examples/assets/` line in `.gitignore`.
- The bad `FIELDSHOW_ENGRAVE_TIMEOUT` test now covers abc, 0, -1, inf and nan. The parser already rejected all of them (`0 < value < inf`), so it is unchanged.
- The decision is logged in `docs/ops/AUTONOMOUS-DECISIONS-2026-10-22.md`.

## Migration

Old `field_image` values (`examples/assets/field.png`, absolute paths, `/tmp/fieldshow-*/field.png`) still load. The page and other intents work, but `/api/field-image` now gives a silent 404 and the value stays in the show. To fix one, re-run `fieldshow import-image show.json <img> -o show.json`, which writes `images/field.<ext>` beside the show. Both repo JSONs (`examples/fanfare.json`, `docs/adr/0004-evidence/in/show.json`) have null, so nothing in the repo needs it.

## DoD → tests (`tests/test_field_image.py` unless noted)

There is one refused-value table, `BAD`, with 28 rows. `_plant()` puts a real file at every row that is a creatable path in the show dir, so each refusal is the rule's doing, not a missing file. `images/dir.png` is a directory and `images/unread.png` is mode 0. Both table tests run their checks as a non-root uid. When pytest itself is root (a root container), `_unprivileged()` forks, drops to uid/gid 65534 and runs the check there, so the unreadable row is never skipped.

| Item | Test |
|---|---|
| Intent 422 and show unchanged for every BAD row: traversal, absolute, symlink-out, NUL, `%2e`, non-canonical (`./`, `x/..`, `//`, absolute path to the real image), and the B1 name/ext set (`x.png\n`, `x.txt.png`, `x.png.txt`, `a.b.png`, a 65-char name, `.png`, Kelvin, `imageſ/`, `.svg`, `.json`, `field.txt`, `sub/x.png`), plus S1 `dir.png` and T1 `unread.png` | `test_intent_rejects_field_image_outside_images[*]` (28) |
| Serve 404 for the same 28 rows written straight into show.json; no secret, `/etc/passwd` or planted bytes served | `test_serve_404s_a_tampered_field_image_in_the_show_json[*]` (28) |
| Accepted controls: a 64-char name and `x.PNG`, 200 with the right bytes | `test_boundary_names_are_accepted_and_served[*]` (2) |
| S3: `apply_intent` refuses on its own (what `fieldshow apply` relies on) | `test_apply_intent_itself_refuses_a_bad_field_image` |
| S2: the CLI `import-image` writes `<dir of -o>/images/field.png`, not cwd | `test_cli_import_image_writes_beside_the_output_not_cwd` (subprocess, cwd elsewhere) |
| Non-image upload gives 415 and the show is unchanged | `test_non_image_upload_is_415_and_leaves_the_show` |
| `images/` symlinked outside the show | `test_serve_404s_when_images_dir_points_outside_the_show` |
| Symlink loop or unreadable `images/` gives 404, not 500 | `test_serve_404s_on_a_symlink_loop_or_unreadable_images_dir` (the chmod half skips as root; the unreadable-file row above covers root) |
| Legit image served with correct bytes; set and clear | `test_legit_field_image_is_served_and_can_be_set_and_cleared` |
| Upload stored as a marker; traversal filename ignored | `test_upload_is_stored_as_a_marker_and_served` |
| Timeout 0, -1, inf, nan, abc | `tests/test_part_pdfs.py::test_bad_engrave_timeout_fails_the_build_and_keeps_old_pdfs[*]` |

## Mutants (round 2)

MUTANTS_R2

Round 1's "All CAUGHT" covered only its own 8 mutants. The Reviewer ran 29 and found 13 survivors: I1, `is_file`→`exists`, E-RT on 3.13, E-VE, 8 regex mutants, and the CLI cwd mutant. All of them are in the table above.

## Reviewer nits folded in (T-0005)

- N2: Python 3.13 and later do not raise on a symlink loop in `Path.resolve()` (non-strict). The path comes back unresolved and `is_file()` is False, so the result is 404 either way. Python 3.12, the image's interpreter, raises RuntimeError, so the RuntimeError catch stays in both the part-PDF and field-image guards.
- N3: T-0005 mutant M6 is relabelled "not observable", not "equivalent". The summary in `docs/PENDING-HANDOFF.md` now reads 21 CAUGHT, 1 EQUIVALENT (M3), 1 NOT OBSERVABLE (M6).

## Parked

- Merge and redeploy belong to the parent. The Tester and Reviewer gates on this SHA are pending.
- `deploy-maximum.md` gained first-time setup, a clean `git archive` export, and rollback via a `pre-*` tag. No Sysadmin notes were readable on the box or nimo, so it follows the brief. maximum was not touched.
- The page still draws no field image (`index.html` has no reference; PROMPT-CARD's "draws it under the dots" predates #3).

## Evidence

EVIDENCE_R2
