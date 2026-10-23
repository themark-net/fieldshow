# Pending handoff

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
