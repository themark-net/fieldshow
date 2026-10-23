# Handoff: fieldshow #4 code slice (2026-10-23)

Branch `build/4-code-slice` in worktree `tmp/4-code-slice`, based on `origin/main` `645a388`. Pushed to origin after the r2 verification pass again after the r3 fix round, and after the r4 fix round (new commits only, no rebase, no force). No PR. Mark's checkout at `/home/mark/DEVELOP/fieldshow` was not touched. Issue themark-net/fieldshow#4 only.

The "field image not drawn" item is still open and will be filed separately. `src/fieldshow/web/static/index.html` was not edited.

## What changed

1. **Scratch file.** `POST /api/image` already unlinked `upload*` in a `finally`. The upload tests now assert nothing matching `upload*` remains under `app.state.assets` after a 200 and after a 415. (r3) The scratch write itself now sits inside the `try`, so a failed or short write (for example ENOSPC) leaves no partial file.
2. **Magic bytes.** The handler in `web/app.py` sniffs PNG (`\x89PNG\r\n\x1a\n`), JPEG (`\xff\xd8\xff`), GIF (`GIF87a` / `GIF89a`), and WebP (`RIFF` then `WEBP` at byte 8). Anything else is 415. The scratch name and `images/field.<ext>` use that type (`.png`, `.jpg`, `.gif`, `.webp`), not the client filename. An extensionless PNG is `images/field.png`. `drill/image.py` and `fieldshow import-image` still trust the source suffix.
3. **`_unprivileged`** (test harness, root only). (r3) `_reachable_by_others(tmp_path, root)` adds only `o+x`, only where missing, and only to dirs from `tmp_path` up to pytest's own temp root (`pytest-of-<user>` when pytest made it, else the `--basetemp` dir). If any dir above that root lacks `o+x`, nothing is changed and the test is skipped with that dir named; (r4) under root, or with `FIELDSHOW_REQUIRE_CHILD=1`, it fails instead, so the in-image runs cannot skip the child silently. A guardian process (own session, set up before `_start_guard` returns, holding a pipe) restores the modes and SIGKILLs an unreaped child whenever the pipe closes, including when pytest is SIGKILLed. The child sets `PR_SET_PDEATHSIG` (SIGKILL, via `ctypes` `prctl`) after `setuid`, so it dies with its parent. The child's `TMPDIR` and `tempfile.tempdir` point at a private dir under `tmp_path`; the parent removes only that dir and never scans the shared TMPDIR. `_wait_child` polls `WNOHANG` for at most 60s, then SIGKILLs, reaps, and raises.
4. **Long suffix.** If the client filename has a suffix, it must be in `FIELD_IMAGE_SUFFIXES` (case-insensitive) or the handler returns 415 before reading the body or writing a file. A 300-character suffix is 415 for a PNG body and for junk. `evil.exe` with PNG bytes is 415 too.
5. **Temp dir.** `create_app` still uses `tempfile.mkdtemp(prefix="fieldshow-")`. (r4) The FastAPI lifespan shutdown removes it when the server stops on SIGTERM, SIGINT or a clean stop. `weakref.finalize(app, shutil.rmtree, path, True)` stays as the backup: it removes the dir when an app that never ran a lifespan is collected, or at a normal interpreter exit. It does not run on SIGTERM, because uvicorn 0.54 re-raises the signal after its graceful shutdown (exit 143); that is why r3 still leaked.

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
- `85e1b1b` docs(#4): r3 handoff and decisions
- `42df551` docs(#4): r4 root cause for the SIGTERM temp dir leak
- `275829e` test(#4): r4 red-first: SIGTERM/SIGINT serve leak, lifespan, fail-not-skip, riffless WEBP, guard session race
- `c84e22e` fix(#4): remove the assets dir in the lifespan shutdown (SIGTERM leak)
- this docs commit (r4 handoff, decisions, root-cause outcome)

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

Add `--user 1000:1000` for the non-root in-image run. The r3 runs used the same steps through the runner `tmp/4-code-slice.inimage.sh` (in the repo, gitignored, not in git): `sh tmp/4-code-slice.inimage.sh fieldshow:4-code-slice`, then the same with `--user 1000:1000`.

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

## Round 4 (Tester FAIL at `85e1b1b`)

Root cause (confirmed on nimo at `85e1b1b`, private `TMPDIR`): `fieldshow serve` stopped with SIGTERM exits 143 and leaves its `fieldshow-*` dir; SIGINT exits 0 and removes it. Both logs say "Application shutdown complete". uvicorn 0.54 re-raises SIGTERM after its graceful shutdown, so the process dies by the signal and neither the `weakref.finalize` nor atexit runs. Detail: [ROOT-CAUSE](ROOT-CAUSE-4-code-slice-2026-10-23.md#round-4-tester-fail-at-85e1b1b-reviewer-pass-2026-10-23).

Fix: `create_app` gives FastAPI a lifespan whose `finally` removes the assets dir (and whose startup recreates it if a previous lifespan removed it). The finalizer stays as the backup. Production change is in `src/fieldshow/web/app.py` only.

Harness changes (tests only):

- **Fail, not skip (Tester S1 / Reviewer SF-A, mutant U3).** `_reachable_by_others` fails instead of skipping when `_require_child()` is true: under root by default, or with `FIELDSHOW_REQUIRE_CHILD=1`; `=0` turns it off. The in-image runs pass `-e FIELDSHOW_REQUIRE_CHILD=1`. The two tests that need the skip (skip test, kill probe) set `=0` explicitly. Under U3 the root run now shows 60 failures instead of 60 silent skips.
- **Guardian session race (found by the new group-kill test).** `_start_guard` returned before the guardian had called `setsid`, so `kill -9 -<pgid>` right after could take the guardian with pytest. It now waits for a byte the guardian writes after `setsid`. At `85e1b1b` helpers the group-kill test failed 5 of 5 runs (`0o701` left); it passes 5 of 5 now.

### New tests

| Test | Pins | Runs as |
| --- | --- | --- |
| `test_stopped_server_leaves_no_assets_dir[SIGTERM]` | B1: `python -m fieldshow serve --host 127.0.0.1 --port <free>`, wait for `/api/health`, SIGTERM, no `fieldshow-*` left in its private `TMPDIR` | both |
| `test_stopped_server_leaves_no_assets_dir[SIGINT]` | B1: same with SIGINT (already worked; pins it) | both |
| `test_lifespan_shutdown_removes_the_assets_dir` | B1: clean stop via the lifespan, no GC; a second lifespan gets its dir back | both |
| `test_upload_rejects_bytes_that_are_not_an_image[riffless.webp-...]` | SF2 / T3: `XXXX....WEBP` without `RIFF` is 415, nothing written | both |
| `test_a_default_run_reaches_tmp_path_without_skipping` | U3 on the host: with pytest's own `pytest-of-*` root, the reach must not skip or fail | both |
| `test_reach_fails_instead_of_skipping_when_the_child_is_required` | SF1: `FIELDSHOW_REQUIRE_CHILD=1` turns the skip into a failure, no modes changed | both |
| `test_child_exits_if_its_parent_is_already_gone` | Reviewer: the `getppid()` check exits 1 | both |
| `test_guard_leaves_a_mode_that_someone_else_changed` | Reviewer: the guardian does not restore a mode it did not set | both |
| `test_guard_survives_a_kill_of_pytests_process_group` | Reviewer: the guardian has its own session; a group SIGKILL of a fake pytest still gets the mode restored within 5s | both |

The existing `test_process_exit_removes_the_assets_dir` still covers a clean interpreter exit.

### Red-first (one method)

Method, used for every number here: a copy of the tracked files at `275829e` (the new tests) with `src/` equal to `85e1b1b` (`git diff --quiet 85e1b1b -- src`), and the two r4 harness fixes undone in that copy (the fail-not-skip branch and the guardian ready read/write). The whole of `tests/test_web.py` and `tests/test_field_image.py` is run, no `-k`:

```bash
cd /tmp/fs4r4/red && PYTHONPATH=src /home/mark/DEVELOP/fieldshow/.venv/bin/python -m pytest -p no:cacheprovider -v tests/test_web.py tests/test_field_image.py
```

Host uid 1000: `4 failed, 102 passed, 3 skipped`. Every failure is a new test. Per new test:

| New test | Red result |
| --- | --- |
| `test_lifespan_shutdown_removes_the_assets_dir` | FAILED |
| `test_stopped_server_leaves_no_assets_dir[SIGTERM]` | FAILED (dir left) |
| `test_stopped_server_leaves_no_assets_dir[SIGINT]` | PASSED (SIGINT already cleaned up) |
| `test_upload_rejects_bytes_that_are_not_an_image[riffless.webp-...]` | PASSED (behaviour already right; pinned by mutant 13) |
| `test_a_default_run_reaches_tmp_path_without_skipping` | PASSED (root detection already right; pinned by mutant 12) |
| `test_reach_fails_instead_of_skipping_when_the_child_is_required` | FAILED (`skipped: ... has no o+x`) |
| `test_child_exits_if_its_parent_is_already_gone` | PASSED (already right; pinned by mutant 14) |
| `test_guard_leaves_a_mode_that_someone_else_changed` | PASSED (already right; pinned by mutant 15) |
| `test_guard_survives_a_kill_of_pytests_process_group` | FAILED (`0o701` left) |

So the new tests were **4 failed, 5 passed** by this method. In-image root, same copy, the six `test_field_image.py` additions (`-k` on their names, via `/tmp/fs4r3/inimage-src.sh`): 2 failed (fail-not-skip, group kill), 4 passed.

### Mutation proof (r4): 18 mutants, 18 killed

Each ran in its own `git archive` copy of `c84e22e`; worktree sha256 of every tracked file unchanged before and after (only this handoff, edited by hand, differs), `git status` clean apart from it.

| # | Mutant | Killed by | Where |
| --- | --- | --- | --- |
| 1-10 | r3 mutants (table above) | same tests as r3 (4 also by the fail-not-skip test; 5 also by the group-kill test) | as r3 |
| 11 | Lifespan cleanup removed (B1) | lifespan test, SIGTERM serve test | host |
| 12 | U3: `_TEMP_ROOT = base` | default-run reach test (host); 60 tests fail instead of skip (root) | host and root |
| 13 | T3: no `RIFF` check | riffless WEBP case | host |
| 14 | No `getppid()` check | parent-already-gone test | host |
| 15 | Guardian restores without the mode check | someone-else-changed test | host |
| 16 | Guardian without `setsid` | group-kill test | host |
| 17 | `_require_child()` always false | fail-not-skip test | host and root |
| 18 | `_start_guard` returns without waiting for `setsid` | group-kill test, guard test, kill -9 `home-searchable` (the guardian's ready write then hits a closed pipe and it exits without restoring) | host |

### Test counts at the r4 head

| Mode | Result | `fieldshow-*` before -> after |
| --- | --- | --- |
| Host uid 1000, run 1 | 137 passed, 5 skipped (30.8s) | 1248 -> 1248 |
| Host uid 1000, run 2 | 137 passed, 5 skipped (31.0s) | 1248 -> 1248 |
| Host uid 1000, run 3 | 137 passed, 5 skipped (30.8s) | 1248 -> 1248 |
| In-image root, `-e FIELDSHOW_REQUIRE_CHILD=1` | 139 passed, 3 skipped (51.6s) | 0 -> 0 |
| In-image uid 1000, `-e FIELDSHOW_REQUIRE_CHILD=1` | 139 passed, 3 skipped (48.3s) | 0 -> 0 |

Skips: host 2 LilyPond, 2 root-only, the kill probe; root 2 "root ignores directory permissions", the kill probe; in-image uid 1000 2 root-only, the kill probe. No reach skip anywhere. `/tmp/pytest-of-mark` was `0700` after every host run and no `killprobe-*` was left. Image rebuilt locally as `fieldshow:4-code-slice` (`874890554472`), not pushed.

## Residual

- **Field image not drawn.** Still open; `index.html` was not changed. Out of scope here; it will be filed as its own issue (Reviewer N6).
- **Upload size cap and `nosniff` for polyglot uploads.** Already tracked in a separate fieldshow issue (#5). Not changed in this slice.
- **`import-image` (CLI).** Still trusts the source suffix and does not sniff. Kept as residual: the CLI is run by the operator on their own file, `drill/image.py` is marked stable, and the LAN-facing path (`/api/image`) does sniff.
- **Root run and dir modes.** While a uid 65534 child runs, dirs from `tmp_path` up to pytest's own temp root that lacked `o+x` have it. Nothing above that root is ever changed: the test skips instead. If pytest is SIGKILLed mid-child, the guardian restores those modes and kills the child within moments. (r4) A SIGKILL of pytest's process group is covered: the guardian is in its own session before `_start_guard` returns. A SIGKILL aimed at the guardian itself (by pid, or `kill -9 -1` by the same uid) is not covered; then only dirs inside pytest's own temp root keep `o+x`, and the child still dies through `PR_SET_PDEATHSIG`.
- **FastAPI cache.** The GC test clears every `cache_clear` on `fastapi.dependencies.models` because those caches hold the route callables, which close over the app. This depends on FastAPI private names; a FastAPI upgrade that moves them fails that test loudly until the clear follows. The process-exit test covers the server behaviour.
- **Docker image** `fieldshow:4-code-slice` (`874890554472`) is local on nimo, not pushed or deployed. `docker rmi fieldshow:4-code-slice` removes it (DevBot or Sysadmin, not Mark).
- **OQ-0005.** The page stays a no-login LAN app. No new port, no auth. Tests use TestClient only.
- **Cleanup item: pre-existing `/tmp/fieldshow-*` on nimo.** 1248 dirs, left from earlier servers and test runs before the r4 fix (SIGTERM-stopped servers leaked one each). Not deleted in this slice, on purpose. Someone with the go-ahead can remove them once nothing running uses them, for example `find /tmp -maxdepth 1 -name 'fieldshow-*' -user mark -mmin +60 -exec rm -rf {} +`.
- **SIGTERM exit code.** The server still exits 143 on SIGTERM: that is uvicorn re-raising the signal, and it now happens after the lifespan cleanup. A hard SIGKILL of the server still leaves its dir; nothing in-process can run then.
- **Gate.** Tester and Reviewer both need to pass the new head SHA.

## Parked 2026-10-23 (fieldshow #4 code slice, round 5 in progress)

Mark took fieldshow off the active projects list on 2026-10-23 (PDT). Work stopped mid round 5.

- **Branch:** `build/4-code-slice`, worktree `tmp/4-code-slice`. Nothing was merged to main and no PR exists.
- **Last gated pin:** `89337fd`. Reviewer and Tester both FAILed it.
- **Commits after it:** `e34ab59` (r5 tests) and `794702b` (WIP src fix), plus this docs commit. None of these have been gated.

### Done in round 5 (after `89337fd`)

- **`e34ab59`, test.** Red-first tests:
  - a dir planted at the freed `fieldshow-*` name between two lifespans (foreign dir, and `images` symlinked to a victim);
  - the upload refusing a symlinked `images/`;
  - SIGTERM the moment the dir appears during startup, 10 runs.
  
  The old name-reuse assertion is gone. `_start_guard` now checks that the guardian's ready message is its own session id, so the ready byte provably comes after `setsid` (Reviewer G2). There is also a test that `_require_child()` is true under root with no env var set (Reviewer R2).
  
  At `89337fd` src, 4 of these failed on the host:
  - both planted-dir cases;
  - the images-link case;
  - SIGTERM during startup, which leaked 10 of 10 runs (rc -15).
- **`794702b`, WIP fix in `src/fieldshow/web/app.py`.** `_AssetsDir` makes the dir with `mkdtemp` in lifespan startup, or on first upload when there is no lifespan. It remembers st_dev/st_ino, and uses or `rmtree`s the dir only while `lstat` shows that same real dir, owned by the euid, mode 0700. Otherwise it makes a fresh dir and never touches the foreign one. `create_app` no longer makes a dir. The upload returns 500 for a symlinked or non-dir `images/`. The field-image read path uses only a verified dir.
  - Host suite with this change: 143 passed, 5 skipped. That was one run; the x3 runs were not done.
  - Reviewer's `relife.py` probe, in-image with a 1777 shared dir and a uid 65534 planter:
    - **At `89337fd`, server root:** the planted 0777 dir was used, `field.png` was written into the root-owned victim, and `theirs.txt` was deleted.
    - **At `89337fd`, server uid 1000:** the planted dir was used, and the upload failed with EACCES writing through the link.
    - **With `794702b`, server root and server uid 1000:** a fresh 0700 dir owned by the server uid was used, the victim stayed empty, and the planted dir and `theirs.txt` survived.
    - **Script change:** with `794702b`, Reviewer's script as written reads `app.state.assets` before any lifespan, gets `None`, and so plants at `None`. I used a copy that reads the path inside the first lifespan. Both copies are at `/tmp/fs4r5/` on nimo.

### Open blockers (from the `89337fd` verdicts)

1. **Reviewer M1-r4: lifespan dir takeover.** `app.py` used `mkdir(exist_ok=True)` at the freed name, so a second lifespan took over a foreign dir. Fixed in WIP `794702b` with tests in `e34ab59`. Not yet re-gated:
   - no x3 host runs;
   - no in-image runs;
   - no mutants (including new ones for the dev/ino check and for the images-symlink refusal).
2. **Tester BL1: orphaned serve Popen** in `tests/test_web.py`, `test_stopped_server_leaves_no_assets_dir` (lines 118-143 at `89337fd`). The startup test added in `e34ab59` uses the same bare Popen. If pytest is SIGKILLed or SIGTERMed mid-test, the server keeps listening and keeps its dir. **Not started.**
   - Planned fix: start the server with a `preexec_fn` that sets `PR_SET_PDEATHSIG` (SIGTERM, so it shuts down gracefully and removes its dir) and then checks `getppid()`.
   - Planned test: a kill probe that SIGKILLs and SIGTERMs a forked pytest-like parent, then asserts the server is gone and the port is closed.

### SIGTERM during startup (Reviewer SF-1)

At `89337fd`, the dir was made in `create_app` before uvicorn installed its signal handlers, so a SIGTERM in that window killed the process and leaked the dir. Reviewer measured 7 of 24 runs at 0.41-0.46s; the r5 test measured 10 of 10 when the signal is sent the moment the dir appears. `794702b` moves the dir into lifespan startup, which runs under uvicorn's handlers; the r5 test passes 10 of 10 with it. It has not been gated.

### Other open items

- **SIGHUP and SIGQUIT** still leak the dir (Tester SF1). Not handled. One option is to map them to SIGTERM in `cmd_serve` before `uvicorn.run`.
- **Tester should-fixes, not started:**
  - resolve the assets path at create time (a TMPDIR symlink retargeted mid-run; the dev/ino check in `794702b` already refuses the `rmtree` of a decoy, but the path is not resolved);
  - clean up the dir on the health-timeout failure path of the serve test;
  - the `_free_port` bind/close race (planned: `--port 0` and read the port from uvicorn's log, which reports it);
  - a comment on the ready-after-setsid ordering. Partly done: `_start_guard` now carries a comment and a runtime check.
- **Pre-existing `/tmp/fieldshow-*` on nimo:** 1248 dirs, left in place on purpose. Cleanup item, nothing deleted.
- **"Field image not drawn":** not filed. It needs its own issue; nothing was filed for it.
- **Local Docker image `fieldshow:4-code-slice`** (`874890554472`) on nimo: built locally, not pushed, not removed.
- **Unchanged residuals:**
  - CLI `import-image` still trusts the suffix;
  - `nosniff` and the size cap are tracked in #5;
  - SIGKILL of the server leaves its dir;
  - SIGTERM exits 143 (uvicorn re-raises the signal);
  - a SIGKILL aimed at the guardian itself;
  - the GC test depends on FastAPI's private cache names.
- **Scratch on nimo:** `/tmp/fs4r4/`, `/tmp/fs4r5/` (probes, mutant scripts). Nothing removed.

To resume: do Tester BL1 and the should-fixes on top of `794702b`. Then re-run red-first (one method), the host suite x3, in-image root and uid 1000 with `-e FIELDSHOW_REQUIRE_CHILD=1`, all mutants old and new, and the `relife` probe. Then re-gate with Reviewer and Tester.
