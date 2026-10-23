# Autonomous decisions, 2026-10-23

The session picked a reversible default, wrote it down, and kept going. Issue themark-net/fieldshow#4 code slice only. No push, no PR.

| Choice | Alternatives | Why |
| --- | --- | --- |
| Item 1 is a test lock. Production `finally: incoming.unlink` stays. | A second cleanup path | The unlink was already on both the 415 path and the success path. The suite never looked. |
| Magic sniff lives in `web/app.py`. `drill/image.py` and `fieldshow import-image` still trust the file suffix. | Sniff inside `import_image` | AGENTS.md marks `drill/image.py` and `model.py` stable. The CLI behaviour is unchanged. |
| JPEG bytes are stored as `.jpg`. A client suffix `.jpeg` is still allowed, then the bytes pick the stored name. | Store `.jpeg` when the client said `.jpeg`; add a new suffix | The issue says `jpeg -> .jpg`. `.jpeg` is already in `FIELD_IMAGE_SUFFIXES`. |
| 415 detail is `field image must be png, jpg, webp, or gif`. | A separate "bad magic" sentence | Same sentence `import_image` already raises. Tests lock status, the show, and the files, not the wording. |
| A client suffix is checked only when the filename has one, case-insensitively, and before `image.read()` or any scratch write. Extensionless names are decided by the bytes. | Reject extensionless names; check the suffix after the sniff | An extensionless PNG must be accepted as `images/field.png`. A 300-character suffix must 415 even when the body is a PNG. |
| `evil.exe` with PNG bytes is in the suffix test, beside the 300-character cases. | Only the 300-character names | A length cap would 415 the long name and still store `evil.exe` full of PNG bytes. The allowlist is the rule. The long PNG body is what goes red if the early check is removed and the sniff stays. |
| `_open_up_dirs` chmods from `tmp_path` through `stop` inclusive, then stops. `_unprivileged` passes `tmp_path.parent` (pytest's basetemp). `/` and `/tmp` remain hard stops. | Stop before chmodding the basetemp; also chmod `pytest-of-<user>` | The basetemp is mode `0o700` and is this run's tree. Its parent is the shared pytest root and stays `0o700`. |
| `_wait_child` polls `WNOHANG` and SIGKILLs at the deadline (60s from `_unprivileged`). The hang test calls it with 1s on a daemon thread and joins for 10s. | `signal.alarm`; a bare `waitpid` with `WNOHANG` once | Alarm is process-global. One poll would miss a child that exits a moment later. The join bound is what keeps a red run from hanging the suite. |
| The chmod test restores ancestor modes in a `finally`. | Leave the red run's chmod in place | The old walk opens directories above the test, including `/tmp/pytest-of-<user>`. The assertion fails, then the modes go back. |
| Upload temp dir cleanup is `weakref.finalize(app, shutil.rmtree, path, True)` only. | An ASGI shutdown handler as well | Tests build the app and often never run lifespan. The finalizer covers `gc.collect()` and interpreter exit. `ignore_errors=True` keeps a second cleanup quiet. |
| The GC test clears every `cache_clear` on `fastapi.dependencies.models` before `del app`. | Expect `gc.collect()` to collect the app with those caches full | Those caches hold the route callables, and the callables close over the app, so the finalizer would not run until process exit. |
| `index.html` was not edited. The "field image not drawn" note stays open. | Draw the image while the upload gate was open | The issue text for this slice says that item is out of scope. |
| Docker in-image pytest was not run, as root or otherwise. | Build the image and run pytest as root | The host run is uid 1000. A root container is the only place the fork path runs, and scoping the chmod may leave `/tmp/pytest-of-root` at `0o700`, which uid 65534 cannot traverse. |
