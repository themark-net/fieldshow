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
