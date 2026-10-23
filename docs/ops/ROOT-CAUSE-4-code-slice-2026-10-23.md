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
