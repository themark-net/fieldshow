# Handoff: fieldshow #4 deploy-doc slice (2026-10-22)

Branch `build/4-deploy-doc`, from main `22e7d61`. Docs only: `docs/ops/deploy-maximum.md`. maximum was not touched.

## Done (Reviewer notes from verdict-a2281f33 and verdict-22e7d611, as listed in #4)
- N1 (22e7d611): the current-target rollback, the pre-`a803da2` fallback and its undo name the legacy images by ID (`e0e247aeb14e`, `0f631c29aa48`), not by tag, so a retired `pre-a803da2-to-e786df3` tag cannot break them. Every rollback checks its image and backups before the first `cp`, so a missing piece stops it with nothing changed.
- N2: the generic rollback runs the health check before the retire; a failed check leaves the set `pre-` for a rerun.
- N3: removed "Rollback leaves the `pre-*` tag ... in place" and reworded the single-set sentence for `used-*`.
- N4: added a prune block for `used-*` sets (tags and `show.json`/`parts` backups), keeping the newest `KEEP`.
- Also folded (a2281f33 notes): Update stops on more than one `pre-<OLD>-to-*` set instead of `head -n1` (N1); the fallback undo says it does not restore `show.json.pre-e786df3` and why that is equivalent (N3); the stop message mentions ssh failure (N5); `import-image` reformatting `intent.json` is noted (N10); the generic rollback lists first and takes `OLD=`/`NEW=` on its first line (N11, still one edit).

## Left
- a2281f33 N4 (set named after the first attempted NEW): documented, unchanged.
- #4 code items (upload scratch-file test, extensionless upload / magic bytes, field image not drawn, Tester's `_unprivileged` chmod scope, waitpid timeout, long suffix 500, `/tmp/fieldshow-*` leak): not docs; untouched.

## Evidence
`bash -n` on all 12 bash blocks (placeholders filled). Mocked dry run (ssh, docker, rsync, curl; hex SHAs): normal rollback; missing tag and missing parts backup stop before any `cp` with data unchanged; failed health leaves the set `pre-`, a rerun retires it; prune with KEEP=1 leaves the newest `used-*` and all `pre-*`/legacy items; legacy rollback works with its tag retired and stops before `cp` when the ID is missing; G, H, B4, empty SHA and two-set cases pass.
