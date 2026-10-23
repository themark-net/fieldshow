# Handoff: fieldshow #4 code slice (2026-10-23)

Branch `build/4-code-slice` in worktree `tmp/4-code-slice`, based on `origin/main` `645a388`. Pushed to origin after the r2 verification pass and again after the r3 fix round (new commits only, no rebase, no force). No PR. Mark's checkout at `/home/mark/DEVELOP/fieldshow` was not touched. Issue themark-net/fieldshow#4 only.

The "field image not drawn" item is still open. `src/fieldshow/web/static/index.html` was not edited.

## What changed

1. **Scratch file.** `POST /api/image` already unlinked `upload*` in a `finally`. The upload tests now assert nothing matching `upload*` remains under `app.state.assets` after a 200 and after a 415. (r3) The scratch write itself now sits inside the `try`, so a failed or short write (for example ENOSPC) leaves no partial file.
2. **Magic bytes.** The handler in `web/app.py` sniffs PNG (`\x89PNG\r\n\x1a\n`), JPEG (`\xff\xd8\xff`), GIF (`GIF87a` / `GIF89a`), and WebP (`RIFF` then `WEBP` at byte 8). Anything else is 415. The scratch name and `images/field.<ext>` use that type (`.png`, `.jpg`, `.gif`, `.webp`), not the client filename. An extensionless PNG is `images/field.png`. `drill/image.py` and `fieldshow import-image` still trust the source suffix.
3. **`_unprivileged`** (test harness, root only). (r3) `_reachable_by_others(tmp_path, root)` adds only `o+x`, only where missing, and only to dirs from `tmp_path` up to pytest's own temp root (`pytest-of-<user>` when pytest made it, else the `--basetemp` dir). If any dir above that root lacks `o+x`, the test is skipped with that dir named and nothing is changed. A guardian process (own session, holding a pipe) restores the modes and SIGKILLs an unreaped child whenever the pipe closes, including when pytest is SIGKILLed. The child sets `PR_SET_PDEATHSIG` (SIGKILL, via `ctypes` `prctl`) after `setuid`, so it dies with its parent. The child's `TMPDIR` and `tempfile.tempdir` point at a private dir under `tmp_path`; the parent removes only that dir and never scans the shared TMPDIR. `_wait_child` polls `WNOHANG` for at most 60s, then SIGKILLs, reaps, and raises.
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
- `a7d2e06` docs(#4): r2 verification, root-run fix, 11/11 mutants, decisions and handoff

At `a7d2e06` the branch was **29** commits ahead of `645a388` (an earlier report said 28; the list above has 29).

Round 3, after the Reviewer FAIL at `a7d2e06`, done by hand (no Build run):

- `02f44fd` docs(#4): root cause for the r3 MUSTs; drop em dashes from headings
- `400ca75` test(#4): r3 child gets a private TMPDIR, walk stops at the pytest root, guardian and PDEATHSIG survive kill -9; pin empty body 415 and a failed scratch write
- `d3a0b4a` fix(#4): write the upload scratch file inside the try so a failed write leaves nothing
- `68d06c5` test(#4): the guardian test fails within 5s instead of hanging when the child is left running
- `aae846b` test(#4): find pytest's temp root by name prefix and owner, so a uid with no passwd entry works
- this docs commit (handoff, decisions)

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

Add `--user 1000:1000` for the non-root in-image run. The r3 runs used the same steps through the runner `tmp/4-code-slice.inimage.sh` (outside the repo): `sh tmp/4-code-slice.inimage.sh fieldshow:4-code-slice`, then the same with `--user 1000:1000`.

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

## Round 3 (Reviewer FAIL at `a7d2e06`)

Both MUSTs were in the root-only test harness. Production `src/` still has no chmod, fork, or setuid. Root causes: [ROOT-CAUSE-4-code-slice-2026-10-23.md](ROOT-CAUSE-4-code-slice-2026-10-23.md#round-3-reviewer-fail-at-a7d2e06-2026-10-23).

### New tests

| Test | Pins | Runs as |
| --- | --- | --- |
| `test_child_cleanup_spares_a_fieldshow_dir_it_did_not_create` | M1: a uid 65534 `fieldshow-*` sibling with a payload, planted in the shared TMPDIR while the child runs (pipe handshake), survives | root |
| `test_reach_skips_instead_of_widening_above_the_pytest_root` | M2: a dir above the temp root without `o+x` means skip, and no mode changes | both |
| `test_kill_9_of_pytest_mid_child_leaves_no_wider_mode_and_no_child[home-searchable]` | M2: a separate pytest with `--basetemp` under a home-like tree is SIGKILLed mid-child; the basetemp goes back to no other bits and the child is gone | both |
| `test_kill_9_of_pytest_mid_child_leaves_no_wider_mode_and_no_child[home-750]` | M2: a 0750 home above the basetemp makes the probe skip; no mode changes, no child | both |
| `test_the_child_dies_when_its_parent_is_sigkilled` | M2: `PR_SET_PDEATHSIG`, set after the uid drop | both (uid drop under root) |
| `test_guard_kills_an_unreaped_child_and_restores_modes_when_its_pipe_closes` | M2: the guardian on its own | both |
| `test_child_wait_is_bounded_at_60s` | N7: the child wait bound is finite and at most 60s | both |
| `test_failed_scratch_write_leaves_no_partial_file` | SF1: a short write that raises ENOSPC leaves no `upload*` | both |
| `test_empty_upload_is_415_and_writes_nothing` | SF2: empty body is 415, nothing written | both |
| `test_kill_probe_child_sleeps` | helper started by the kill -9 test; skipped in a normal run | n/a |

`test_unprivileged_child_leaves_no_upload_dirs` now also asserts no `child-tmp-*` is left under `tmp_path`.

### Red-first at `a7d2e06`

The new tests appended to the `a7d2e06` test file, with `a7d2e06` `src/` (a `git archive` copy, the worktree untouched):

- Host uid 1000: **4 failed**, 2 passed, 2 skipped. Failed: the scratch write (real: `upload.png` left), the 60s bound and both kill -9 cases (the r3 helpers do not exist there). Passed: the empty body test (behaviour was already right; pinned by mutant 2) and the existing hang test.
- In-image root: **5 failed**, 1 passed. All behavioural except the bound test: the planted sibling was deleted (`FileNotFoundError` on its payload); after kill -9 the basetemp stayed `0o701`; the 0750 home became `0o751`; the scratch file was left.

### Mutation proof (r3): 10 mutants, 10 killed

Each mutant ran in its own `git archive` copy of the head; the worktree files were unchanged before and after (sha256 of `app.py`, `test_field_image.py`, `test_web.py` checked, `git status` clean).

| # | Mutant | Killed by | Where |
| --- | --- | --- | --- |
| 1 | Sweep every uid 65534 `fieldshow-*` in the shared TMPDIR after the child (Reviewer M16) | sibling test | root |
| 2 | Empty body stored as `.png` (Reviewer M10) | empty body test | host |
| 3 | `_CHILD_WAIT_SECONDS = 10**9` (Reviewer M18) | 60s bound test | host |
| 4 | Walk to `/` with no skip (the `a7d2e06` behaviour) | skip test, kill -9 `home-750` | host and root |
| 5 | Guardian does not restore modes | kill -9 `home-searchable`, guardian test | host |
| 6 | Guardian does not kill the child | guardian test | host |
| 7 | No `PR_SET_PDEATHSIG` | parent-death test | host |
| 8 | `PR_SET_PDEATHSIG` before `setuid` (the credential change clears it) | parent-death test | root |
| 9 | Child keeps the shared TMPDIR | no-upload-dirs test | root |
| 10 | Scratch write back outside the `try` | scratch write test | host |

### Test counts at the r3 head

| Mode | Result | `fieldshow-*` before -> after |
| --- | --- | --- |
| Host uid 1000, run 1 | 128 passed, 5 skipped (29.6s) | 1248 -> 1248 |
| Host uid 1000, run 2 | 128 passed, 5 skipped (29.7s) | 1248 -> 1248 |
| Host uid 1000, run 3 | 128 passed, 5 skipped (29.5s) | 1248 -> 1248 |
| In-image root | 130 passed, 3 skipped | 0 -> 0 |
| In-image uid 1000 | 130 passed, 3 skipped | 0 -> 0 |

`/tmp/pytest-of-mark` was `0700` after every host run, and no `killprobe-*` dir was left. Host skips: 2 LilyPond, 2 root-only, the kill probe. Root skips: 2 "root ignores directory permissions", the kill probe. In-image uid 1000 skips: 2 root-only, the kill probe. The image was rebuilt locally from this worktree as `fieldshow:4-code-slice` (`c263a40755b9`), not pushed.

The first in-image uid 1000 run errored in setup (94 errors): `getpass.getuser()` raises for a uid with no passwd entry. The temp root is now found by the `pytest-of-` prefix and owner, and the rerun above is green.

## Residual

- **Field image not drawn.** Still open; `index.html` was not changed. Proposed as its own new issue so it keeps a tracker if #4 closes (Reviewer N6).
- **Upload size cap and `nosniff` for polyglot uploads.** Already tracked in a separate fieldshow issue. Not changed in this slice.
- **`import-image` (CLI).** Still trusts the source suffix and does not sniff. Kept as residual: the CLI is run by the operator on their own file, `drill/image.py` is marked stable, and the LAN-facing path (`/api/image`) does sniff.
- **Root run and dir modes.** While a uid 65534 child runs, dirs from `tmp_path` up to pytest's own temp root that lacked `o+x` have it. Nothing above that root is ever changed: the test skips instead. If pytest is SIGKILLed mid-child, the guardian restores those modes and kills the child within moments. A SIGKILL of the guardian itself at the same moment (for example killing the whole session) is not covered; then only dirs inside pytest's own temp root keep `o+x`, and the child still dies through `PR_SET_PDEATHSIG`.
- **FastAPI cache.** The GC test clears every `cache_clear` on `fastapi.dependencies.models` because those caches hold the route callables, which close over the app. This depends on FastAPI private names; a FastAPI upgrade that moves them fails that test loudly until the clear follows. The process-exit test covers the server behaviour.
- **Docker image** `fieldshow:4-code-slice` (`c263a40755b9`) is local on nimo, not pushed or deployed. `docker rmi fieldshow:4-code-slice` removes it (DevBot or Sysadmin, not Mark).
- **OQ-0005.** The page stays a no-login LAN app. No new port, no auth. Tests use TestClient only.
- **Pre-existing `/tmp/fieldshow-*`** on nimo: 1248, left in place.
- **Gate.** Tester and Reviewer both need to pass the new head SHA.
