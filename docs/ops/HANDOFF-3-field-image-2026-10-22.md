# Handoff: #3 field_image path restriction, 2026-10-22

Branch `build/3-field-image`, off `a803da2`. Tester and Reviewer both passed `e786df3`, and main was fast-forwarded to `e786df3`. No PR. Later commits on the branch change docs only.

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

Each mutant ran in a fresh `git archive HEAD` copy, in `fieldshow:t0005` as the host uid, 4 at a time. The worktree was never patched. The runner is `tmp/mutants/run_3r2.py` (gitignored). The logs on nimo are `/tmp/fs-3r2-mutants-pass1.log` (all 31, at `27046a5`) and `/tmp/fs-3r2-mutants-b.log` (re-run at `27b72b1`: CLEAN 100 passed, both `is_file` mutants, E-VE).

**31 mutants: 30 CAUGHT, 1 SURVIVED (E-VE, equivalent), 0 other survivors.** Pass 1 had 3 survivors: S-isfile drop, S-isfile→exists, and E-VE. The new `open()` readability check also refuses a directory (IsADirectoryError), so `is_file` was pinned only by something `open()` does not refuse. A FIFO is that case: opening one blocks. `test_a_fifo_named_like_an_image_is_refused_without_blocking` kills both, as confirmed in the re-run.

As root (a separate in-image run, as uid 0), S-readable drop `open()` also goes red: `[images/unread.png]` fails at intent and at tamper through the 65534 fork. So the root path is not a no-op.

| Mutant | Result | Failed | First failing tests |
|---|---|---|---|
| I1 drop apply_intent raise | CAUGHT | 1 | test_apply_intent_itself_refuses_a_bad_field_image |
| I2 drop handler file check | CAUGHT | 4 | test_intent_rejects_field_image_outside_images[images/out.png]; test_intent_rejects_field_image_outside_images[images/missing.png] |
| I-both | CAUGHT | 29 | test_intent_rejects_field_image_outside_images[../secret.png]; test_intent_rejects_field_image_outside_images[images/../../secret.png] |
| I3 no ValueError->422 | CAUGHT | 24 | test_intent_rejects_field_image_outside_images[../secret.png]; test_intent_rejects_field_image_outside_images[images/../../secret.png] |
| S-serve raw path | CAUGHT | 37 | test_intent_rejects_field_image_outside_images[../secret.png]; test_intent_rejects_field_image_outside_images[images/../../secret.png] |
| S-regex drop serve re-check | CAUGHT | 15 | test_serve_404s_a_tampered_field_image_in_the_show_json[ABS_LEGIT]; test_serve_404s_a_tampered_field_image_in_the_show_json[images/./field.png] |
| S-contain drop is_relative_to(images) | CAUGHT | 2 | test_intent_rejects_field_image_outside_images[images/out.png]; test_serve_404s_a_tampered_field_image_in_the_show_json[images/out.png] |
| S-root drop images-in-root | CAUGHT | 1 | test_serve_404s_when_images_dir_points_outside_the_show |
| S-isfile drop | CAUGHT (survived pass 1; the FIFO test was added) | 1 | test_a_fifo_named_like_an_image_is_refused_without_blocking |
| S-isfile exists() | CAUGHT (survived pass 1; the FIFO test was added) | 1 | test_a_fifo_named_like_an_image_is_refused_without_blocking |
| S-readable drop open() | CAUGHT | 2 | test_intent_rejects_field_image_outside_images[images/unread.png]; test_serve_404s_a_tampered_field_image_in_the_show_json[images/unread.png] |
| E-all except->ZeroDivision | CAUGHT | 3 | test_intent_rejects_field_image_outside_images[images/unread.png]; test_serve_404s_a_tampered_field_image_in_the_show_json[images/unread.png] |
| E-VE drop ValueError | SURVIVED (equivalent: NUL is the only ValueError source and the regex refuses it first) | 0 | - |
| E-OS drop OSError | CAUGHT | 3 | test_intent_rejects_field_image_outside_images[images/unread.png]; test_serve_404s_a_tampered_field_image_in_the_show_json[images/unread.png] |
| E-RT drop RuntimeError | CAUGHT | 1 | test_serve_404s_on_a_symlink_loop_or_unreadable_images_dir |
| Roots drop show_dir | CAUGHT | 32 | test_intent_rejects_field_image_outside_images[../secret.png]; test_intent_rejects_field_image_outside_images[images/../../secret.png] |
| Roots drop upload dir | CAUGHT | 2 | test_upload_is_stored_as_a_marker_and_served; test_web.py::test_page_and_frame_share_one_show |
| R-search | CAUGHT | 6 | test_intent_rejects_field_image_outside_images[ABS_LEGIT]; test_intent_rejects_field_image_outside_images[images/x.png\n] |
| R-match | CAUGHT | 4 | test_intent_rejects_field_image_outside_images[images/x.png\n]; test_intent_rejects_field_image_outside_images[images/x.png.txt] |
| R-match-dollar | CAUGHT | 2 | test_intent_rejects_field_image_outside_images[images/x.png\n]; test_serve_404s_a_tampered_field_image_in_the_show_json[images/x.png\n] |
| R-dots-in-name | CAUGHT | 4 | test_intent_rejects_field_image_outside_images[images/x.txt.png]; test_intent_rejects_field_image_outside_images[images/a.b.png] |
| R-slash-in-name | CAUGHT | 2 | test_intent_rejects_field_image_outside_images[images/sub/x.png]; test_serve_404s_a_tampered_field_image_in_the_show_json[images/sub/x.png] |
| R-any-name | CAUGHT | 17 | test_intent_rejects_field_image_outside_images[images/./field.png]; test_intent_rejects_field_image_outside_images[images/x/../field.png] |
| R-len-unbounded | CAUGHT | 2 | test_intent_rejects_field_image_outside_images[images/nnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnn.png]; test_serve_404s_a_tampered_field_image_in_the_show_json[images/nnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnn.png] |
| R-ext-any | CAUGHT | 7 | test_intent_rejects_field_image_outside_images[images/x.svg]; test_intent_rejects_field_image_outside_images[images/x.json] |
| R-ext-txt-allowed | CAUGHT | 5 | test_intent_rejects_field_image_outside_images[images/x.json]; test_intent_rejects_field_image_outside_images[images/field.txt] |
| R-no-ignorecase | CAUGHT | 1 | test_boundary_names_are_accepted_and_served[images/x.PNG] |
| R-no-ascii | CAUGHT | 3 | test_intent_rejects_field_image_outside_images[images/\u212a.png]; test_serve_404s_a_tampered_field_image_in_the_show_json[images/\u212a.png] |
| U drop upload 415 | CAUGHT | 1 | test_non_image_upload_is_415_and_leaves_the_show |
| C import base = cwd | CAUGHT | 1 | test_cli_import_image_writes_beside_the_output_not_cwd |
| T-nan timeout <= 0 | CAUGHT | 3 | test_part_pdfs.py::test_bad_engrave_timeout_fails_the_build_and_keeps_old_pdfs[abc]; test_part_pdfs.py::test_bad_engrave_timeout_fails_the_build_and_keeps_old_pdfs[inf] |

Round 1's "All CAUGHT" covered only its own 8 mutants. The Reviewer ran 29 and found 13 survivors: I1, `is_file`→`exists`, E-RT on 3.13, E-VE, 8 regex mutants, and the CLI cwd mutant. All of them are in the table above.

## Reviewer nits folded in (T-0005)

- N2: Python 3.13 and later do not raise on a symlink loop in `Path.resolve()` (non-strict). The path comes back unresolved and `is_file()` is False, so the result is 404 either way. Python 3.12, the image's interpreter, raises RuntimeError, so the RuntimeError catch stays in both the part-PDF and field-image guards.
- N3: T-0005 mutant M6 is relabelled "not observable", not "equivalent". The summary in `docs/PENDING-HANDOFF.md` now reads 21 CAUGHT, 1 EQUIVALENT (M3), 1 NOT OBSERVABLE (M6).

## Parked

- Main is at `e786df3` (fast-forward after the double PASS). Redeploying maximum belongs to Sysadmin and the parent; follow `docs/ops/deploy-maximum.md`.
- `deploy-maximum.md` gained first-time setup, a clean `git archive` export, and rollback via a `pre-*` tag. Sysadmin's corrections are folded in: the update reruns `fieldshow build`, the IPv6 pull retry, the current rollback image `fieldshow:pre-a803da2`, and moving the override aside for pre-`a803da2` images. No Sysadmin notes were readable on the box or nimo, so it follows the brief. maximum was not touched.
- The page still draws no field image (`index.html` has no reference; PROMPT-CARD's "draws it under the dots" predates #3).

## Evidence

Run on nimo at `27b72b1`. That is the last code and test commit; the commit after it changes docs only.

- `docker build -t fieldshow:t0005 .`: exit 0, image id `sha256:290a7eac8bd6a0cdace1f4edf36a562af63d1422dbc345fb863b12dee9bfcf5f`. The log is `/tmp/fs-3r2-build.log`.
- In-image pytest (`fieldshow:t0005`, Python 3.12, host uid, `:ro` mount): `100 passed, 1 warning in 42.61s`
- In-image as root, `tests/test_field_image.py`: `65 passed, 1 skipped`. The skip is the chmod half of the images-dir test (`root ignores directory permissions`). The unreadable-file rows ran through the 65534 fork and passed.
- Host pytest (Python 3.14): `98 passed, 2 skipped, 1 warning in 26.88s`. The 2 skips are the LilyPond engraving tests.
- Files in the worktree not owned by the host uid: 0.
