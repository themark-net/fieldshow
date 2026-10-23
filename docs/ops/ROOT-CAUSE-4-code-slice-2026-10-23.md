# Root cause: fieldshow #4 code slice (2026-10-23)

Worktree `tmp/4-code-slice`, branch `build/4-code-slice`, base `origin/main` `645a388`. Issue themark-net/fieldshow#4 only. The "field image not drawn" note is out of scope.

Baseline before any edit: `98 passed, 2 skipped` in 26.84s. `/tmp/fieldshow-*` went from 435 to 510 (delta 75). Pre-existing dirs were left in place.

## Item 1 — scratch upload file is not asserted

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

## Item 5 — `/tmp/fieldshow-*` leak

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


## Item 2 — extensionless upload and magic bytes

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

## Item 3 — `_unprivileged` chmod scope and `waitpid`

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

## Item 4 — long filename suffix returns 500

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
