# Handoff: fieldshow #4 code slice (2026-10-23)

Branch `build/4-code-slice` in worktree `tmp/4-code-slice`, based on `origin/main` `645a388`. Pushed to origin after the r2 verification pass (new commits only, no force). No PR. Mark's checkout at `/home/mark/DEVELOP/fieldshow` was not touched. Issue themark-net/fieldshow#4 only.

The "field image not drawn" item is still open. `src/fieldshow/web/static/index.html` was not edited.

## What changed

1. **Scratch file.** `POST /api/image` already unlinked `upload*` in a `finally`. The upload tests now assert nothing matching `upload*` remains under `app.state.assets` after a 200 and after a 415. No production change.
2. **Magic bytes.** The handler in `web/app.py` sniffs PNG (`\x89PNG\r\n\x1a\n`), JPEG (`\xff\xd8\xff`), GIF (`GIF87a` / `GIF89a`), and WebP (`RIFF` then `WEBP` at byte 8). Anything else is 415. The scratch name and `images/field.<ext>` use that type (`.png`, `.jpg`, `.gif`, `.webp`), not the client filename. An extensionless PNG is `images/field.png`. `drill/image.py` and `fieldshow import-image` still trust the source suffix.
3. **`_unprivileged`.** (r2) `_reachable_by_others(tmp_path)` opens `tmp_path` to `0755` like its contents, and adds only `o+x` (search) to each ancestor up to `/` that lacks it, for the duration of the child, then restores every mode exactly. The first version stopped at basetemp and broke the root run (below). `_wait_child` polls `WNOHANG` for 60s, then SIGKILLs, reaps, and raises. The parent also removes `fieldshow-*` dirs the uid 65534 child created, because the child leaves via `os._exit` and its finalizers never run.
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

- `44d295e` docs(#4): hand off the code slice

Verification pass r2, done by hand (no new Build run):

- `8986fc2` docs(#4): root cause for the root-run child and the surviving unlink mutant
- `a16fb29` test(#4): wrap the dir opening in _reachable_by_others (no behaviour change)
- `d0eea90` test(#4): ancestors get o+x only and are restored; scratch removed when import fails late
- `14c8008` fix(#4): child reaches tmp_path via o+x on ancestors, restored after; parent removes the child's upload dirs
- `f9a14d1` test(#4): as root, the uid 65534 child leaves no fieldshow-* dirs
- this docs commit (handoff, decisions, root-cause r2)

## How to run

From this worktree:

```bash
PYTHONPATH=src /home/mark/DEVELOP/fieldshow/.venv/bin/python -m pytest -q -p no:cacheprovider
```

In-image, as root (the only place the uid 65534 fork path runs). The worktree is mounted read-only and copied into the container, so nothing root-owned lands on the host:

```bash
docker build -t fieldshow:4-code-slice .
docker run --rm -v "$PWD:/work:ro" -e HOME=/tmp fieldshow:4-code-slice sh -c \
  'cp -r /work /tmp/w && cd /tmp/w && python -m venv /tmp/v --system-site-packages && . /tmp/v/bin/activate && pip install -q -e ".[dev]" && pytest -q -p no:cacheprovider'
```

Add `--user 1000:1000` for the non-root in-image run.

## Tests

Baseline before any edit: `98 passed, 2 skipped` in 26.84s. That run grew `/tmp/fieldshow-*` from 435 to 510 (delta 75).

Build's three runs at `44d295e`: `119 passed, 2 skipped` each, `/tmp/fieldshow-*` 1072 -> 1072. Reproduced independently at `44d295e`: same counts, 1072 -> 1072 three times.

Final head (r2), host uid 1000, three runs back to back:

| Run | Result | `/tmp/fieldshow-*` before | after |
| --- | --- | --- | --- |
| 1 | 120 passed, 3 skipped (28.51s) | 1162 | 1162 |
| 2 | 120 passed, 3 skipped (28.64s) | 1162 | 1162 |
| 3 | 120 passed, 3 skipped (28.49s) | 1162 | 1162 |

Host skips: the two LilyPond engraving tests, and `test_unprivileged_child_leaves_no_upload_dirs` (root only). 1072 -> 1162 between passes is the verification's own red runs (mutant 5 and the `origin/main` `app.py` run), not the suite. Pre-existing dirs were not deleted.

In-image (`fieldshow:4-code-slice`, image `0afc453c5de8`, Python 3.12.13), final head:

| User | Result | `fieldshow-*` in container after |
| --- | --- | --- |
| root | 121 passed, 2 skipped (both "root ignores directory permissions") | 0 |
| 1000 | 122 passed, 1 skipped (root-only test) | 0 |

At `44d295e` the same root run was `56 failed, 63 passed, 2 skipped`.

## Red-first evidence

r2 additions (details in the root-cause doc):

- **Item 3 r2.** Root in-image at `44d295e`: 56 failed. Host test on the wrapped old helper: 1 failed, `no o+x` on `/tmp/pytest-of-mark` and three dirs below.
- **Item 1 r2.** The only-on-success unlink mutant survived at `44d295e` (the 415-after-write path is unreachable now). The new late-failure test kills it.
- **All fixes reverted.** HEAD tests on `origin/main` `app.py`: 16 failed. `origin/main` returns 500 for a 306-character filename.

Build's original evidence:

- **Item 1.** New assertions against the handler with the `finally` unlink removed: both upload tests failed, leaving `upload.png` and `upload.exe`. Against the real handler they pass. Full suite stayed `98 passed, 2 skipped`.
- **Item 2.** On the suffix-only handler: `12 failed, 1 passed`. The pass is the extensionless PNG. Extensionless text and `fake.png` returned 200. JPEG named `photo.png` was stored as `images/field.png`.
- **Item 3.** On the extracted old helpers: `above` became `0o755`, and `_wait_child` was still blocked at the 10s join on a child that sleeps for an hour. `/tmp/pytest-of-mark` was mode `700` before and after (the test restores ancestor modes).
- **Item 4.** With the sniff in place and no suffix check: PNG bytes plus a 300-character suffix returned 200 `images/field.png`. Junk with that suffix was already 415. `evil.exe` with PNG bytes returned 200.
- **Item 5.** `gc.collect()` left `/tmp/fieldshow-u8nuh5n_`. A subprocess with its own `TMPDIR` left `fieldshow-fcq2trmi`.

## Mutant tally

Build reported 7 mutants killed. Re-run at `44d295e`: 6 killed, **1 survived** (unlink only on success; equivalent there because no HTTP request reaches the 415-after-write branch any more). Fixed with a late-failure test.

Final head: **11 mutants, 11 killed, 0 survived**, every file restored byte-equal (sha256 and `git diff --quiet`). 9 on the host, 2 in-image as root. Table in [ROOT-CAUSE-4-code-slice-2026-10-23.md](ROOT-CAUSE-4-code-slice-2026-10-23.md#mutation-proof-r2-final-head).

## Residual

- **Field image not drawn.** Still open. `index.html` was not changed.
- **`import-image` (CLI).** Still trusts the source suffix and does not sniff. Kept as residual: the CLI is run by the operator on their own file, `drill/image.py` is marked stable, and the LAN-facing path (`/api/image`) does sniff. Moving the sniff into `import_image` later would cover both.
- **Root run widens ancestors briefly.** While each uid 65534 child runs, ancestors that lacked `o+x` (e.g. `/tmp/pytest-of-root`) have it; modes are restored after. A SIGKILL of pytest mid-child would leave `o+x` (search only) on them; pytest re-tightens its own `pytest-of-<user>` on the next run.
- **Child upload-dir cleanup** matches dirs owned by uid 65534 named `fieldshow-*` created during the child. Another uid 65534 process writing such dirs at the same moment could be swept; not a real case in the test image.
- **FastAPI cache.** The GC test clears `fastapi.dependencies.models` caches because they hold the route callables, which close over the app. A FastAPI upgrade that moves those caches will fail that test until the clear follows them. In the server, the dir is removed at process exit.
- **`tmp/` not gitignored.** Worktrees under `tmp/` show as `?? tmp/` in Mark's checkout. Logged as a decision, not changed here.
- **Docker image** `fieldshow:4-code-slice` (`0afc453c5de8`) was built on nimo for the in-image runs. Not pushed, not deployed. `docker rmi fieldshow:4-code-slice` removes it.
- **OQ-0005.** The page stays a no-login LAN app. No new port, no auth. Tests use TestClient only.
- **Pre-existing `/tmp/fieldshow-*`** on nimo: 1162, left in place.
