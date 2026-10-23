# Root cause: fieldshow #4 code slice (2026-10-23)

Worktree `tmp/4-code-slice`, branch `build/4-code-slice`, base `origin/main` `645a388`. Issue themark-net/fieldshow#4 only. The "field image not drawn" note is out of scope.

Baseline before any edit: `98 passed, 2 skipped` in 26.84s. `/tmp/fieldshow-*` went from 435 to 510 (delta 75). Pre-existing dirs were left in place.

## Item 1: scratch upload file is not asserted

### Symptom

Reviewer SF1. The upload tests never look in the server temp dir. `test_upload_is_stored_as_a_marker_and_served` (`tests/test_field_image.py:218`) and `test_non_image_upload_is_415_and_leaves_the_show` (`tests/test_field_image.py:280`) check the HTTP result and the show. They do not check that the `upload*` scratch file is gone. A change that stops deleting it stays green.

### Where

`src/fieldshow/web/app.py:86-94`. The handler writes `app.state.assets / f"upload{suffix}"` and unlinks it in a `finally`.

### Hypothesis

The unlink is already on both paths (415 and success). The defect is the missing assertion, not a missing `unlink`. Deleting the `finally`, or running the unlink only after a successful `import_image`, leaves `upload*` in `app.state.assets` and the current suite still passes.

### Planned surgical fix

Test-only. No production change. Assert that `app.state.assets` contains no `upload*` entry after a 200 upload and after a 415.

### Planned test

Through `TestClient`: POST a PNG and glob `upload*`; POST `evil.exe` with a non-image body, expect 415, and glob `upload*` again. Both globs empty. The show image still serves.

### Planned mutant

Delete `finally: incoming.unlink(missing_ok=True)` (`app.py:93-94`), or move that unlink so it runs only on success. The new 415 assertion must fail for the success-only form. The new success assertion must fail if the success path stops unlinking.

### Red-first evidence

The production `finally` already deletes the scratch file, so the new assertions are green against unmodified `app.py`. Red evidence is the same assertions against the mutant (the `finally` unlink removed, file restored afterwards, `git diff --exit-code` clean, sha256 `956f2372708c2ddb5028b6649ab29db0c864ec623979beb4fa82c067b165128f` both before and after).

```
PYTHONPATH=src /home/mark/DEVELOP/fieldshow/.venv/bin/python -m pytest -q -p no:cacheprovider \
  tests/test_field_image.py::test_upload_is_stored_as_a_marker_and_served \
  tests/test_field_image.py::test_non_image_upload_is_415_and_leaves_the_show
```

`2 failed`. `test_upload_is_stored_as_a_marker_and_served` left `upload.png`. `test_non_image_upload_is_415_and_leaves_the_show` still returned 415 and left `upload.exe`.

### Fix

No production edit. The `finally` unlink was already correct. The assertions are the lock. Full suite after that commit: `98 passed, 2 skipped` in 26.75s.

### Mutation proof

`app.py` copied to `/tmp`, edited in place, tests run, then copied back. `git diff --exit-code` clean after each restore.

| Item | Mutant | Killed by | sha256 before | sha256 after |
| --- | --- | --- | --- | --- |
| 1 | Delete the `finally` unlink | `test_upload_is_stored_as_a_marker_and_served` (left `upload.png`), `test_non_image_upload_is_415_and_leaves_the_show` (left `upload.exe`) | `956f2372708c2ddb5028b6649ab29db0c864ec623979beb4fa82c067b165128f` | same |
| 1 | Unlink only in `else` (success path) | `test_non_image_upload_is_415_and_leaves_the_show` left `upload.exe`. The success test stayed green | `956f2372708c2ddb5028b6649ab29db0c864ec623979beb4fa82c067b165128f` | same |
| 2 | Handler uses `Path(filename).suffix or ".png"` again and does not sniff | `test_upload_rejects_bytes_that_are_not_an_image` (`notes`, `fake.png` returned 200) and `test_upload_stores_the_sniffed_type` (`photo.png` stored `images/field.png`). 12 failed, 1 passed | `9d004ff0be46b014d8a37999c38848fadbb796153b19eeaf741640065a8330a7` | same |
| 3 | `_open_up_dirs` ignores `stop` and walks to `/` or `/tmp` | `test_open_up_dirs_stops_at_the_scoped_root`: `above` is `0o755` | `ac1e4b36021ef2af04c08b580eac19d0b529da3decbca207f2fc0e35d91ebb6b` | same |
| 3 | `_wait_child` is `os.waitpid(pid, 0)` again | `test_wait_child_kills_a_hung_child_within_the_timeout` failed at the 10s join | `ac1e4b36021ef2af04c08b580eac19d0b529da3decbca207f2fc0e35d91ebb6b` | same |
| 4 | Early client-suffix check removed, sniff left in place | `test_disallowed_suffix_is_415_before_anything_is_written` PNG + 300-char suffix returned 200 `images/field.png`. Junk + long suffix stayed 415. `evil.exe` + PNG bytes also returned 200 | `0c588aa4defc5af929715774b23b93621e9734e48bd4c3123b70f508de4e30c5` | same |
| 5 | `weakref.finalize(...)` removed | `test_assets_dir_is_removed_when_the_app_is_collected` (dir still there after `gc.collect()`) and `test_process_exit_removes_the_assets_dir` (subprocess left `fieldshow-*`) | `352a6d5f94a95fd0d8671e7cc039deaaa68b5afca7fdd811b1133aee53efbffd` | same |

## Item 5: `/tmp/fieldshow-*` leak

### Symptom

Every `create_app` call leaves a directory under the temp dir. Nothing removes it. The baseline suite (98 passed, 2 skipped) moved `/tmp/fieldshow-*` from 435 to 510, delta 75. Pre-existing directories were not deleted.

### Where

`src/fieldshow/web/app.py:66`:

```python
app.state.assets = Path(tempfile.mkdtemp(prefix="fieldshow-"))
```

There is no shutdown hook and no finalizer.

### Hypothesis

`tempfile.mkdtemp` creates the directory and returns. The `FastAPI` instance is the only owner. When the test drops the client, or the process exits, nothing calls `rmtree`. One directory per call, including the ones `TestClient` builds. A finalizer registered on the app runs when the app is collected and again for leftovers at interpreter exit, which covers both an in-process `gc.collect()` and a subprocess that just exits.

### Planned surgical fix

Right after `mkdtemp`, `weakref.finalize(app, shutil.rmtree, path, True)`. The callback does not reference the app. `ignore_errors=True` so a second cleanup is quiet. No lifespan handler: these tests build the app and never run ASGI shutdown.

### Planned test

(a) `create_app()`, remember `app.state.assets`, `del` the app, `gc.collect()`. The directory is gone.

(b) A subprocess with `TMPDIR` set to the test's `tmp_path` imports `create_app`, calls it, and exits 0. `tmp_path.glob("fieldshow-*")` is empty.

After the fix, one full suite does not increase the count of `/tmp/fieldshow-*`. Existing directories stay.

### Planned mutant

Remove the `weakref.finalize` line. (a) still sees the directory after `gc.collect()`. (b) still sees `fieldshow-*` under `TMPDIR`.

### Red-first evidence

```
PYTHONPATH=src /home/mark/DEVELOP/fieldshow/.venv/bin/python -m pytest -q -p no:cacheprovider --tb=short \
  tests/test_web.py::test_assets_dir_is_removed_when_the_app_is_collected \
  tests/test_web.py::test_process_exit_removes_the_assets_dir
```

`2 failed`.

- After `del app` and `gc.collect()`, `/tmp/fieldshow-u8nuh5n_` still existed.
- The subprocess left `fieldshow-fcq2trmi` under its `TMPDIR`.

### Fix

`weakref.finalize(app, shutil.rmtree, path, True)` runs on collection and at interpreter exit. The in-process test clears `fastapi.dependencies.models` callable caches first: those caches hold the route functions, and the functions close over the app, so `gc.collect()` would not see it. Full suite: `119 passed, 2 skipped` in 28.39s. `/tmp/fieldshow-*` was 1071 before that run and 1071 after (delta 0). Pre-existing directories were left in place.


## Item 2: extensionless upload and magic bytes

### Symptom

`POST /api/image` decides 415 from the client filename suffix only. An extensionless file has an empty suffix, so the handler substitutes `.png` and `import_image` accepts it. A file named `fake.png` whose bytes are not a PNG is stored as `images/field.png`. The stored extension follows the client name, not the bytes.

### Where

`src/fieldshow/web/app.py:86-88`:

```python
suffix = Path(image.filename or "field.png").suffix or ".png"
incoming = app.state.assets / f"upload{suffix}"
incoming.write_bytes(await image.read())
```

`import_image` (`src/fieldshow/drill/image.py:19-21`) then accepts any file whose suffix is in `FIELD_IMAGE_SUFFIXES`. That module stays as it is. The CLI `import-image` path keeps today's suffix check.

### Hypothesis

The upload handler never reads the magic bytes. Empty suffix becomes `.png` before the bytes are considered, so any extensionless payload is a PNG as far as the show is concerned. A `.png` name skips the 415 even when the body is `MZ` or plain text. The scratch name is `upload` plus the client suffix, so the copy `import_image` writes inherits that suffix.

### Planned surgical fix

In `web/app.py` only, sniff the body before trusting it: PNG `\x89PNG\r\n\x1a\n`, JPEG `\xff\xd8\xff`, GIF `GIF87a` / `GIF89a`, WebP `RIFF` + `WEBP` at offset 8. Anything else is 415 and nothing is left under `app.state.assets`. The scratch file and the stored `images/field.<ext>` use the sniffed suffix (`.png`, `.jpg`, `.gif`, `.webp`), and that suffix must be one of `FIELD_IMAGE_SUFFIXES`. The client filename is not used for the stored name. An extensionless real PNG is `images/field.png`.

### Planned test

`TestClient` uploads. Extensionless text and a `.png`-named non-image (plus RIFF/WAVE, a short PNG, a two-byte JPEG) return 415, the show JSON is unchanged, the original field image still serves, and `assets` has no `upload*`. Extensionless PNG bytes are stored as `images/field.png`. JPEG, GIF87a, GIF89a, and WebP bodies are stored as `.jpg`, `.gif`, `.gif`, and `.webp` even when the client name says `.png`. A `.jpeg` name with JPEG bytes is stored as `.jpg`, not `.jpeg`. A `.gif` name with PNG bytes is stored as `.png`. The show directory's `images/field.png` is not overwritten.

### Planned mutant

Put the suffix decision back on the client filename (`Path(filename).suffix or ".png"`) and skip the sniff. Extensionless text is accepted, and a JPEG body named `photo.png` is stored as `images/field.png`.

### Red-first evidence

Against unmodified `app.py` (suffix only):

```
PYTHONPATH=src /home/mark/DEVELOP/fieldshow/.venv/bin/python -m pytest -q -p no:cacheprovider --tb=line \
  tests/test_field_image.py::test_upload_stores_the_sniffed_type \
  tests/test_field_image.py::test_upload_rejects_bytes_that_are_not_an_image
```

`12 failed, 1 passed`. The pass is the extensionless PNG (`yard` -> `images/field.png`), which the suffix fallback already stores that way. The failures:

- `photo.png` + JPEG bytes stored `images/field.png`, not `images/field.jpg`
- `photo.jpeg` stored `images/field.jpeg`
- GIF87a and GIF89a named `.png` stored `images/field.png`
- WebP named `.png` stored `images/field.png`
- PNG bytes named `pic.gif` stored `images/field.gif`
- `notes` (extensionless text), `fake.png`, RIFF/WAVE, a short PNG, `\xff\xd8` alone, and `GIF88a` all returned 200

### Fix

`_sniffed_image_suffix` in `web/app.py` picks `.png` / `.jpg` / `.gif` / `.webp` from the magic bytes, each checked against `FIELD_IMAGE_SUFFIXES`. A miss is 415 before the scratch file is written. `import_image` and the CLI are unchanged. Full suite: `111 passed, 2 skipped` in 26.92s.

## Item 3: `_unprivileged` chmod scope and `waitpid`

### Symptom

As root, `_unprivileged` (`tests/test_field_image.py:109`) chmods every ancestor of `tmp_path` to `0o755` until the path is `/` or `/tmp` (`test_field_image.py:114-117`). Pytest's own basetemp is not the boundary. A temp dir that is not under `/tmp` (a `TMPDIR` under the home directory, for example) gets its parents opened all the way up. The same helper then blocks in `os.waitpid(pid, 0)` (`test_field_image.py:136`). A check that never returns hangs the suite. There is no kill and no deadline.

This session runs as uid 1000, so the `euid == 0` branch does not run here. The two pieces have to be testable without being root.

### Where

`tests/test_field_image.py:114-117` and `tests/test_field_image.py:136`.

### Hypothesis

The chmod walk's only stop is the string `"/" ` or `"/tmp"`, so the scoped root is not an input. `os.waitpid(pid, 0)` waits forever. Extracting those two loops into helpers, without changing what they do, makes the old behaviour callable as uid 1000. The helpers are still wrong until they honor a stop directory and a deadline.

### Planned surgical fix

First extract, behaviour unchanged: `_open_up_dirs(tmp_path, stop)` still walks to `/` or `/tmp` and ignores `stop`. `_wait_child(pid, timeout)` still calls `os.waitpid(pid, 0)` and ignores `timeout`. `_unprivileged` calls them with `stop=tmp_path.parent` (pytest's basetemp for this fixture) and `timeout=60`.

Then change the helpers only. `_open_up_dirs` chmods from `tmp_path` up through `stop` inclusive, and breaks on `stop`, `/`, or `/tmp`, so a directory above `stop` stays `0o700`. `_wait_child` polls `os.WNOHANG` until `timeout` (60s from `_unprivileged`), then `SIGKILL`, reaps, and raises a message that says the child was killed. The `rglob` chmod of directories inside `tmp_path` stays.

### Planned test

No root. `test_open_up_dirs_stops_at_the_scoped_root`: build `above/scoped/nested/inner` under `tmp_path`, mode `0o700`, call `_open_up_dirs(inner, scoped)`. `above` stays `0o700`. `scoped`, `nested`, and `inner` become `0o755`. A `finally` puts every ancestor mode back, including dirs the old walk opens above `tmp_path`.

`test_wait_child_kills_a_hung_child_within_the_timeout`: fork a child that sleeps for an hour, call `_wait_child(pid, 1)` on a daemon thread, `join(10)`. The helper raises within that window and the child is reaped. If the thread is still alive at 10s, the test kills the child and fails. That is what makes the red run finish.

### Planned mutant

1. `_open_up_dirs` ignores `stop` and walks to `/` or `/tmp` again. `above` becomes `0o755`.
2. `_wait_child` blocks in `os.waitpid(pid, 0)`. The daemon-thread join hits 10s and the test fails.

### Red-first evidence

Against the extracted helpers (stop ignored, `waitpid` unbounded). `/tmp/pytest-of-mark` was mode `700` before and after; the test puts ancestor modes back.

```
PYTHONPATH=src /home/mark/DEVELOP/fieldshow/.venv/bin/python -m pytest -q -p no:cacheprovider --tb=line \
  tests/test_field_image.py::test_open_up_dirs_stops_at_the_scoped_root \
  tests/test_field_image.py::test_wait_child_kills_a_hung_child_within_the_timeout
```

`2 failed` in 10.24s.

- `above` was `0o755` (`assert 493 == 448`)
- `_wait_child blocked past 10s on a child that sleeps for an hour; the suite killed it so this run would finish`

### Fix

`_open_up_dirs` chmods through `stop` and then breaks. `_unprivileged` passes `tmp_path.parent`, the pytest basetemp. `_wait_child` polls `WNOHANG` and, at the deadline, sends `SIGKILL`, reaps, and raises. `_unprivileged` still uses 60s. Full suite: `113 passed, 2 skipped` in 28.01s.

As root, `/tmp/pytest-of-<user>` stays `0o700`, so a dropped uid 65534 may still be unable to walk into the default pytest tree. A basetemp whose parent is already traversable (`/tmp`, or `--basetemp` directly under it) is opened. This session did not run the image pytest as root.

## Item 4: long filename suffix returns 500

### Symptom

A client filename whose suffix is about 300 characters used to make `POST /api/image` return 500. `NAME_MAX` is 255. The handler built `upload{suffix}` and called `write_bytes` before `import_image` looked at the suffix, so `OSError` `ENAMETOOLONG` was uncaught.

### Where

Originally `src/fieldshow/web/app.py:86-88` (the pre-sniff handler). After the sniff change the handler is `src/fieldshow/web/app.py:110-119`. It never reads the client suffix. The scratch name is `upload` plus the sniffed suffix, so the 500 is gone, and a real PNG with a 300-character suffix is stored as `images/field.png`.

### Hypothesis

The 500 was the write of an over-long client suffix. Ignoring that suffix (item 2) avoids `ENAMETOOLONG` and also skips the rule that a present suffix must be one of `FIELD_IMAGE_SUFFIXES`. With the sniff left in place, removing only an early allowlist check makes the PNG-plus-long-suffix upload succeed. The check has to run before `write_bytes`, and it has to be the allowlist, not a length cap: `evil.exe` with PNG bytes is short and is also not an image suffix.

### Planned surgical fix

In the upload handler, before reading or writing: if `Path(filename).suffix` is non-empty and `suffix.lower()` is not in `FIELD_IMAGE_SUFFIXES`, return 415. Then sniff as now. Extensionless names still depend on the bytes only. `.PNG` and `.JPEG` stay legal.

### Planned test

`TestClient`, show already serving `images/field.png`. Upload `field.` plus 300 `p`s with PNG bytes, and the same name with junk bytes. Both 415, show JSON unchanged, the original PNG still served, `app.state.assets` empty. Also `evil.exe` with PNG bytes is 415 the same way, so a length-only check does not pass. `FIELD.PNG` with PNG bytes is still 200 and `images/field.png`.

### Planned mutant

Delete only the early suffix check. Leave the sniff. The PNG body with the 300-character suffix returns 200 and is stored. The junk body can still be 415 from the sniff; the PNG body is the one that kills this mutant.

### Red-first evidence

Sniff is in place. No client-suffix check yet.

```
PYTHONPATH=src /home/mark/DEVELOP/fieldshow/.venv/bin/python -m pytest -q -p no:cacheprovider --tb=line \
  tests/test_field_image.py::test_disallowed_suffix_is_415_before_anything_is_written \
  tests/test_field_image.py::test_upload_stores_the_sniffed_type
```

`2 failed, 9 passed`.

- `field.` + 300 `p`s with PNG bytes returned 200 and `images/field.png`
- the same name with junk bytes passed (sniff already returns 415)
- `evil.exe` with PNG bytes returned 200 and `images/field.png`
- `FIELD.PNG` and the other sniffed uploads passed

### Fix

The handler returns 415 when `Path(filename).suffix.lower()` is non-empty and not in `FIELD_IMAGE_SUFFIXES`, before `image.read()` and before any scratch file. The sniff still chooses the stored suffix. Full suite: `117 passed, 2 skipped` in 28.05s.

## Item 3 r2: `_unprivileged` under root after the chmod-scope fix (verification pass, 2026-10-23)

### Symptom

In-image pytest as root (`docker build -t fieldshow:4-code-slice .` at `44d295e`, then pytest in that image as uid 0): **56 failed, 63 passed, 2 skipped**. Every `test_intent_rejects_field_image_outside_images[*]` and `test_serve_404s_a_tampered_field_image_in_the_show_json[*]` case fails with `check failed as uid 65534`. On the host (uid 1000) the fork path never runs, so the suite was green.

### Where

`tests/test_field_image.py` `_unprivileged` → `_open_up_dirs(tmp_path, tmp_path.parent)`.

### Hypothesis

The uid 65534 child needs search (`x`) permission on every ancestor of `tmp_path`. pytest creates `/tmp/pytest-of-root` (and the numbered basetemp) `0700`. The item 3 fix stops at basetemp, so `/tmp/pytest-of-root` stays `0700` and the child gets `EACCES` on every path below it. The pre-fix helper opened it (to `0755`, permanently), which is why `origin/main` passed as root.

### Planned surgical fix

Replace the walk with a context manager `_reachable_by_others(tmp_path)`. For every ancestor of `tmp_path` up to `/` that lacks `o+x`, add only `S_IXOTH` (search, not read or write), run the child, then put every changed mode back exactly. Directories that already have `o+x` (`/`, `/tmp`) are not touched. `tmp_path`'s own tree keeps the existing `0755` treatment. Same code for root and uid 1000; only root forks.

### Planned test

`test_reachable_by_others_adds_only_search_and_restores` (uid 1000, no root needed): a chain `tmp_path/above(0700)/mid(0750)/leaf`. Inside the context every ancestor of `leaf` up to `/` has `o+x`; `above` is `0701` and `mid` `0751` (no read added). After the context, every ancestor's mode equals its snapshot. On nimo `/tmp/pytest-of-mark` is `0700`, so the stop-at-basetemp behaviour is caught there too. End to end: the same in-image root run must go from 56 failed to 0 failed.

### Planned mutants

1. Stop at basetemp again (the `44d295e` behaviour). 2. `chmod(0o755)` instead of `mode | S_IXOTH`. 3. Skip the restore.

## Item 1 r2: the `finally` unlink only-on-success mutant survives at `44d295e`

### Symptom

Re-running mutant "unlink only in `else`" at `44d295e`: **survived** (85 passed). It was killed at `be1c4eb`, before the sniff and the early suffix check.

### Hypothesis

After items 2 and 4, every body that reaches the scratch write is a sniffed image with an allowed suffix, so `import_image` no longer raises `ValueError` on that path. The 415-after-write branch is unreachable from HTTP, so no request can tell `finally` from `else`.

### Planned test

`test_scratch_is_removed_when_import_fails_after_the_write`: monkeypatch `fieldshow.web.app.import_image` to raise `ValueError`, upload a real PNG, expect 415, show unchanged, no `upload*` in assets. This is the handler's cleanup contract for any later failure after the write. No production change.

## Verification pass r2 (2026-10-23, after `44d295e`)

### Red-first evidence

- **Item 3 r2, end to end.** In-image pytest as root at `44d295e`: `56 failed, 63 passed, 2 skipped`, every `_unprivileged` case `check failed as uid 65534`. `/tmp/pytest-of-root` was `drwx------`.
- **Item 3 r2, host.** `test_reachable_by_others_adds_only_search_and_restores` against the wrapped old helper (`a16fb29`): `1 failed` with `no o+x on [.../above, .../test_reachable_by_others_adds_0, /tmp/pytest-of-mark/pytest-821, /tmp/pytest-of-mark]`.
- **Item 1 r2.** `test_scratch_is_removed_when_import_fails_after_the_write` passes on the real handler and fails under the only-on-success mutant. Before it, that mutant survived at `44d295e` (`85 passed`).
- **Root-run upload dirs.** After the chmod fix the in-image root run was green but left 56 `fieldshow-*` dirs owned by uid 65534 (the child exits via `os._exit`, so the finalizer never runs there). `test_unprivileged_child_leaves_no_upload_dirs` (root only) was added with the parent-side cleanup in `14c8008`/`f9a14d1`; its red evidence is the in-image mutant below, not a pre-fix run.
- **All fixes reverted at once.** HEAD tests on `origin/main`'s `app.py`: `16 failed, 72 passed` (sniff, suffix and temp-dir tests). On `origin/main` code a 306-character filename returns **500** for PNG and junk bodies, and an extensionless `notes` text upload returns 200.

### Mutation proof r2 (final head)

Host mutants: `/tmp/fs4-verify/mutate.py` (anchor must match once, file copied aside, edited, targeted tests run, copied back, sha256 and `git diff --quiet` checked). In-image mutants: same copy/restore by hand around `tmp/4-code-slice.inimage.sh`.

| Item | Mutant | Where run | Result |
| --- | --- | --- | --- |
| 1 | delete `finally` unlink | host | killed, 10 failed |
| 1 | unlink only in `else` | host | killed, 1 failed (`..._when_import_fails_after_the_write`) |
| 2 | client suffix again, no sniff | host | killed, 12 failed |
| 3 | `_wait_child` blocks in `waitpid(pid, 0)` | host | killed, hang test fails at 10s join |
| 3 | stop ancestor walk at the first parent (basetemp) | host | killed, `no o+x` on `/tmp/pytest-of-mark` and above |
| 3 | `chmod(0o755)` instead of `mode \| S_IXOTH` | host | killed, `above` is `0o755` |
| 3 | skip the restore | host | killed, modes differ after the block |
| 3 | stop ancestor walk at the first parent | in-image root | killed, 58 failed |
| 4 | early suffix check removed | host | killed, 2 failed |
| 5 | `weakref.finalize` removed | host | killed, 2 failed |
| 5 | parent-side child dir cleanup removed | in-image root | killed, `test_unprivileged_child_leaves_no_upload_dirs`; 57 dirs left |

11 mutants, 11 killed, every file restored byte-equal (sha256 `352a6d5f94a9…` for `app.py`, `50e3f8510aa4…` for `tests/test_field_image.py`). The earlier `_open_up_dirs ignores stop` mutant no longer applies: that helper is gone.

## Round 3 (Reviewer FAIL at `a7d2e06`, 2026-10-23)

Verdict: two MUSTs in the root-only test harness, five should-fixes. Production `src/` has no chmod, fork, or setuid.

### R3 M1: the child cleanup deletes `fieldshow-*` dirs this run did not create

- Symptom: as root with a shared TMPDIR, a uid 65534 `fieldshow-*` dir (with a payload) created by another process while the child ran was deleted.
- Where: `tests/test_field_image.py` `_run_as_nobody` (lines 175-180) and `_nobody_temp_dirs` (190-195) at `a7d2e06`.
- Root cause: the child builds apps in the shared `tempfile.gettempdir()`, so the parent cannot tell its dirs from anyone else's. It guesses by owner, prefix, and a before/after diff. Any matching dir that appears during the window looks like the child's and is removed.
- Planned fix: the parent makes a private dir under `tmp_path`, chowns it to 65534, and the child points `TMPDIR` and `tempfile.tempdir` at it after the uid drop. The parent removes only that dir. Nothing in the shared TMPDIR is scanned or removed.
- Planned test (root only): a parent thread plants a nobody-owned `fieldshow-*` sibling with a payload in the shared TMPDIR while the child is inside its check (pipe handshake, no sleeps). The sibling and payload must survive. Red on `a7d2e06`.
- Planned mutant: put back a sweep of every nobody `fieldshow-*` in the shared TMPDIR after the child. Must die.

### R3 M2: the o+x walk goes up to `/`, and a killed pytest leaves modes widened and the child running

- Symptom: with `--basetemp` or TMPDIR under a home or repo dir, `kill -9` of pytest mid-child left 750 -> 751 and 700 -> 701 on dirs pytest did not create, and the uid 65534 child kept running, re-parented.
- Where: `_reachable_by_others` (lines 127-138) and `_fork_as_nobody` at `a7d2e06`.
- Root cause: two gaps. The walk has no upper bound, so it widens any ancestor. The restore lives in a `finally` in the pytest process, so SIGKILL skips it, and the child has no tie to the parent's life.
- Planned fix:
  - Bound the walk at pytest's own temp root: `pytest-of-<user>` when pytest made it, else the `--basetemp` dir. If any dir above that root lacks `o+x`, `pytest.skip` with the dir named, and change nothing.
  - Before widening, fork a guardian (own session) that holds the read end of a pipe. When the pipe closes for any reason, including pytest being SIGKILLed, it SIGKILLs the child if it was not reaped and puts the modes back.
  - The child sets `PR_SET_PDEATHSIG` to SIGKILL via `ctypes` `prctl`, after `setuid` (a credential change clears it), and exits if the parent is already gone.
- Planned tests: the bound skips and changes no mode; a kill -9 simulation runs pytest in a subprocess with `--basetemp` under a home-like tree, SIGKILLs it mid-child, and asserts every mode is back and the child is gone; a planted 0750 "home" above the root makes the probe skip with no mode change.
- Planned mutants: unbounded walk; no guardian; no `PR_SET_PDEATHSIG`; `_CHILD_WAIT_SECONDS = 10**9`.
