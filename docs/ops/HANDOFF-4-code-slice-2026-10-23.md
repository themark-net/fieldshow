# Handoff: fieldshow #4 code slice (2026-10-23)

Branch `build/4-code-slice` in worktree `tmp/4-code-slice`, based on `origin/main` `645a388`. Not pushed. No PR. Mark's checkout at `/home/mark/DEVELOP/fieldshow` was not touched. Issue themark-net/fieldshow#4 only.

The "field image not drawn" item is still open. `src/fieldshow/web/static/index.html` was not edited.

## What changed

1. **Scratch file.** `POST /api/image` already unlinked `upload*` in a `finally`. The upload tests now assert nothing matching `upload*` remains under `app.state.assets` after a 200 and after a 415. No production change.
2. **Magic bytes.** The handler in `web/app.py` sniffs PNG (`\x89PNG\r\n\x1a\n`), JPEG (`\xff\xd8\xff`), GIF (`GIF87a` / `GIF89a`), and WebP (`RIFF` then `WEBP` at byte 8). Anything else is 415. The scratch name and `images/field.<ext>` use that type (`.png`, `.jpg`, `.gif`, `.webp`), not the client filename. An extensionless PNG is `images/field.png`. `drill/image.py` and `fieldshow import-image` still trust the source suffix.
3. **`_unprivileged`.** `_open_up_dirs` chmods from the test dir up through pytest's basetemp (`tmp_path.parent`) and no further. `_wait_child` polls `WNOHANG` for 60s, then SIGKILLs, reaps, and raises. Both were extracted first so they can be tested as uid 1000.
4. **Long suffix.** If the client filename has a suffix, it must be in `FIELD_IMAGE_SUFFIXES` (case-insensitive) or the handler returns 415 before reading the body or writing a file. A 300-character suffix is 415 for a PNG body and for junk. `evil.exe` with PNG bytes is 415 too.
5. **Temp dir.** `create_app` still uses `tempfile.mkdtemp(prefix="fieldshow-")`. `weakref.finalize(app, shutil.rmtree, path, True)` removes it when the app is collected and when the process exits.

Detail, red output, and the mutant table: [ROOT-CAUSE-4-code-slice-2026-10-23.md](ROOT-CAUSE-4-code-slice-2026-10-23.md). Decisions: [AUTONOMOUS-DECISIONS-2026-10-23.md](AUTONOMOUS-DECISIONS-2026-10-23.md).

## Commits

On top of `645a388`, oldest first:

- `7b8ee42` docs(#4): root-cause hypothesis for the upload scratch file
- `be1c4eb` test(#4): assert upload scratch files are removed
- `15c22e8` docs(#4): item 1 needs no production change
- `0fd7c67` docs(#4): mutation proof for the upload scratch unlink
- `4ffa031` docs(#4): root-cause hypothesis for upload magic bytes
- `c221ec5` test(#4): reject non-images and store the sniffed type
- `11e90a7` fix(#4): sniff image magic before storing an upload
- `7d3fdc4` docs(#4): mutation proof for upload magic sniff
- `52c9500` docs(#4): root-cause hypothesis for _unprivileged
- `d4ab3f5` test(#4): extract _open_up_dirs and _wait_child
- `86a0c6b` test(#4): scope chmod and bound the child wait
- `14c242b` fix(#4): stop chmod at the pytest basetemp and kill a hung child
- `610a0ca` docs(#4): mutation proof for chmod scope and child wait
- `412fd57` docs(#4): root-cause hypothesis for a long upload suffix
- `e0d2d97` test(#4): a disallowed upload suffix is 415 before write
- `f65d460` fix(#4): reject a bad upload suffix before writing
- `892887a` docs(#4): mutation proof for the early suffix check
- `a47bf10` docs(#4): root-cause hypothesis for the fieldshow temp leak
- `0bf0af6` test(#4): the upload temp dir is removed with the app
- `a748419` fix(#4): remove the upload temp dir when the app goes away
- `45360bb` docs(#4): mutation proof for the upload temp dir
- `b8bddb3` docs(#4): record decisions for the code slice

The commit that adds this file follows `b8bddb3`.

## How to run

From this worktree:

```bash
PYTHONPATH=src /home/mark/DEVELOP/fieldshow/.venv/bin/python -m pytest -q -p no:cacheprovider
```

## Tests

Baseline before any edit: `98 passed, 2 skipped` in 26.84s. That run grew `/tmp/fieldshow-*` from 435 to 510 (delta 75).

Final, three runs back to back, each `119 passed, 2 skipped`:

| Run | Result | Time | `/tmp/fieldshow-*` before | after | delta |
| --- | --- | --- | --- | --- | --- |
| 1 | 119 passed, 2 skipped | 28.60s | 1072 | 1072 | 0 |
| 2 | 119 passed, 2 skipped | 28.46s | 1072 | 1072 | 0 |
| 3 | 119 passed, 2 skipped | 28.59s | 1072 | 1072 | 0 |

The 1072 directories were already there (baseline leaks, red runs, and the item 5 mutant). They were not deleted. A full suite no longer adds one.

The two skips are the engraving tests that skip without LilyPond. Same as the baseline.

## Red-first evidence

- **Item 1.** New assertions against the handler with the `finally` unlink removed: both upload tests failed, leaving `upload.png` and `upload.exe`. Against the real handler they pass. Full suite stayed `98 passed, 2 skipped`.
- **Item 2.** On the suffix-only handler: `12 failed, 1 passed`. The pass is the extensionless PNG. Extensionless text and `fake.png` returned 200. JPEG named `photo.png` was stored as `images/field.png`.
- **Item 3.** On the extracted old helpers: `above` became `0o755`, and `_wait_child` was still blocked at the 10s join on a child that sleeps for an hour. `/tmp/pytest-of-mark` was mode `700` before and after (the test restores ancestor modes).
- **Item 4.** With the sniff in place and no suffix check: PNG bytes plus a 300-character suffix returned 200 `images/field.png`. Junk with that suffix was already 415. `evil.exe` with PNG bytes returned 200.
- **Item 5.** `gc.collect()` left `/tmp/fieldshow-u8nuh5n_`. A subprocess with its own `TMPDIR` left `fieldshow-fcq2trmi`.

## Mutant tally

Seven mutants, each copied aside, edited in place, run, and copied back. `git diff --exit-code` was clean and the sha256 matched after every restore. None survived.

| Item | Mutant | Killed by |
| --- | --- | --- |
| 1 | Delete the `finally` unlink | both scratch assertions (`upload.png` and `upload.exe` left behind) |
| 1 | Unlink only on success | `test_non_image_upload_is_415_and_leaves_the_show` left `upload.exe` |
| 2 | Client suffix again, no sniff | 12 failed: `notes` and `fake.png` returned 200; `photo.png` JPEG stored as `images/field.png` |
| 3 | `_open_up_dirs` ignores `stop` | `above` is `0o755` |
| 3 | `_wait_child` blocks in `waitpid` | hang test fails at the 10s join |
| 4 | Early suffix check removed, sniff kept | PNG + 300-character suffix returned 200. Junk stayed 415 |
| 5 | `weakref.finalize` removed | both temp-dir tests: dir remains after `gc.collect()` and after process exit |

## Residual

- **Field image not drawn.** Still open. `index.html` was not changed.
- **Docker.** In-image pytest was not run, as root or otherwise. As root, `_unprivileged` no longer chmods `/tmp/pytest-of-<user>` (it stays `0o700`). A dropped uid 65534 may be unable to walk the default pytest tree. A basetemp whose parent is already traversable still gets opened. This host run is uid 1000, so the fork path did not run.
- **`import-image`.** Still accepts any file with an image suffix and does not sniff. That is deliberate.
- **OQ-0005.** The page stays a no-login LAN app. No new port, no auth.
- **Pre-existing `/tmp/fieldshow-*`.** Left in place. 1072 at the end of the three runs.
- **FastAPI cache.** The GC test clears `fastapi.dependencies.models` caches because they hold the route callables, which close over the app. A FastAPI upgrade that moves those caches will fail that test until the clear follows them.
