# Deploy on maximum

Host: `maximum`, `10.42.0.238`, user `mark`. Docker is already installed. The service listens on port 8876.

Every command below logs in as `mark@maximum`. The `~` paths, `/home/mark/fieldshow-data` and the `--user "$(id -u):$(id -g)"` passed to `docker compose run` all assume that user, so do not shorten it to a host alias that might log in as someone else.

`maximum` does not have the `githu` GitHub key, so `git clone` there fails. Deploy from nimo. Copy a clean export of the target commit, never a working tree: a working tree carries `tmp/` worktrees, mutant scratch and local edits.

## Clean export (nimo)

```bash
SHA=$(git -C ~/DEVELOP/fieldshow fetch origin && git -C ~/DEVELOP/fieldshow rev-parse --short=7 <target ref>)
rm -rf "/tmp/fieldshow-deploy-$SHA" && mkdir "/tmp/fieldshow-deploy-$SHA" &&
git -C ~/DEVELOP/fieldshow archive "$SHA" | tar -x -C "/tmp/fieldshow-deploy-$SHA"
```

`SHA` is the 7-character short SHA. Update and Rollback below use it in tag and backup names, and Update records it in `~/fieldshow-data/DEPLOYED_SHA`.

## First-time setup (maximum)

Do this once, before the first `up`.

```bash
ssh mark@maximum 'mkdir -p ~/fieldshow /home/mark/fieldshow-data && cat > ~/fieldshow/compose.override.yaml' <<'YAML'
services:
  fieldshow:
    volumes:
      - /home/mark/fieldshow-data:/data
    environment:
      FIELDSHOW_SHOW: /data/show.json
YAML
rsync -az --delete --exclude /compose.override.yaml "/tmp/fieldshow-deploy-$SHA/" mark@maximum:fieldshow/ &&
ssh mark@maximum 'cp ~/fieldshow/examples/fanfare.json ~/fieldshow-data/intent.json'
```

`compose.override.yaml` is not in git. `--exclude /compose.override.yaml` keeps `--delete` from removing it. `--delete` does remove every other untracked leftover in `~/fieldshow` on maximum, so keep nothing else there: anything you need to keep (backups, a moved-aside override) goes in `~/fieldshow-data`. Then build `show.json` from the intent, start the service and record what is running:

```bash
ssh mark@maximum 'cd ~/fieldshow && docker compose build fieldshow && docker compose run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp fieldshow \
  fieldshow build /data/intent.json -o /data/show.json && docker compose up -d --no-build --force-recreate fieldshow' &&
ssh mark@maximum "echo '$SHA' > ~/fieldshow-data/DEPLOYED_SHA" &&
curl -fsS http://10.42.0.238:8876/api/health
```

## Update

Before you replace anything, tag the running image and back up the built show, so there is something to roll back to. The replaced SHA comes from `~/fieldshow-data/DEPLOYED_SHA`. Both the tag and the backups are named `pre-<replaced>-to-<new>`, for example `fieldshow:pre-e786df3-to-<new>` with `show.json.pre-e786df3-to-<new>` and `parts.pre-e786df3-to-<new>`. They are taken at most once per replaced SHA: if a `pre-<OLD>-to-*` tag or `show.json.pre-<OLD>-to-*` already exists, the block reuses that set (`$B`) and does not tag or copy again:

```bash
{ OLD=$(ssh mark@maximum 'cat ~/fieldshow-data/DEPLOYED_SHA 2>/dev/null') || true; } && { [ -n "$SHA" ] && [ -n "$OLD" ] && [ "$OLD" != "$SHA" ] || { echo "stop: SHA unset, or DEPLOYED_SHA empty or already $SHA" >&2; false; }; } &&
B=$(ssh mark@maximum "{ docker image ls --format '{{.Tag}}' fieldshow; ls ~/fieldshow-data | sed -n 's/^show[.]json[.]//p'; } | sed -n 's/^pre-\($OLD-to-[0-9a-f]*\)\$/\1/p' | head -n1") && B=${B:-$OLD-to-$SHA} && echo "rollback set: pre-$B" &&
ssh mark@maximum "cd ~/fieldshow && { docker image inspect fieldshow:pre-$B >/dev/null 2>&1 || docker tag \"\$(docker compose images -q fieldshow)\" fieldshow:pre-$B; }" &&
ssh mark@maximum "cd ~/fieldshow-data && { [ -e show.json.pre-$B ] || { rm -rf parts.pre-$B && cp -a parts parts.pre-$B && cp -p show.json show.json.pre-$B; }; }" &&
rsync -az --delete --exclude /compose.override.yaml "/tmp/fieldshow-deploy-$SHA/" mark@maximum:fieldshow/ &&
ssh mark@maximum 'cd ~/fieldshow && docker compose build fieldshow && docker compose run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp fieldshow fieldshow build /data/intent.json -o /data/show.json && docker compose up -d --no-build --force-recreate fieldshow' &&
ssh mark@maximum "echo '$SHA' > ~/fieldshow-data/DEPLOYED_SHA" &&
curl -fsS http://10.42.0.238:8876/api/health
```

The lines are chained with `&&`, so the first failure stops the rest. It stops at once with a message if `DEPLOYED_SHA` is missing, empty or already equals `$SHA` (nothing to do), and the tag fails if no container is running (`images -q` prints nothing).

The block is safe to rerun, with the same `SHA` or a different one, as long as `DEPLOYED_SHA` still names the replaced SHA. The second line finds any existing `pre-<OLD>-to-*` set, so a retry with a fixed `SHA` reuses the tag and backup from the first attempt (named after that first `SHA`) instead of tagging or copying whatever a failed attempt left running or rebuilt. The tag is skipped if `fieldshow:pre-$B` exists and the backup is skipped if `show.json.pre-$B` exists, so a rerun never overwrites the rollback point with the new image or the new show. `show.json.pre-$B` is copied last, so it only exists once `parts.pre-$B` is complete. `DEPLOYED_SHA` changes only after the recreate succeeds; after that a rerun stops at the first line.

`DEPLOYED_SHA` was added after `e786df3` went out. If it is missing on maximum, seed it once with the SHA that is running (`e786df3` today): `ssh mark@maximum "echo e786df3 > ~/fieldshow-data/DEPLOYED_SHA"`.

`fieldshow build` overwrites `show.json` and `parts/`, which is why the backup comes first. The update reruns `fieldshow build` because `serve` only reads `/data/show.json`. Without the build, the new image serves the old `show.json` and the old part PDFs. The build does not touch `images/`, but it rebuilds `field_image` from `intent.json` (see Field picture below).

The old container keeps running until the final `up -d --no-build --force-recreate fieldshow`; the build and the `run --rm` do not stop it. For the few seconds between the `run` and the recreate it serves its old in-memory `show.json` with the new part PDFs, which it reads from disk on each request. Avoid updating while a rehearsal is reading parts.

If `docker compose build` fails while pulling from Docker Hub with `network is unreachable`, maximum's IPv6 route is flaky. Rerun the same block. The old container is still serving, and the tag and backup are kept as they are.

## Rollback

Current rollback target (from Sysadmin, before this naming scheme): image `fieldshow:pre-a803da2-to-e786df3` (`sha256:e0e247aeb14e...`, the `a803da2` image) with data `~/fieldshow-data/show.json.pre-e786df3` (the show `a803da2` built). There is no `parts.pre-*` backup for it.

Older fallback: `fieldshow:pre-a803da2` (`sha256:0f631c29aa48...`) is the image from before `a803da2` (about `6a4b4c8`, before T-0005). It has no `/data` mount support and cannot serve part PDFs. Use it only if the `a803da2` image is unusable; see the last paragraph.

Roll back to the current target:

```bash
ssh mark@maximum 'docker image ls fieldshow' &&
ssh mark@maximum 'cd ~/fieldshow-data && cp -p show.json.pre-e786df3 show.json' &&
ssh mark@maximum 'cd ~/fieldshow && docker tag fieldshow:pre-a803da2-to-e786df3 "$(docker compose config --images fieldshow)" && docker compose up -d --no-build --force-recreate fieldshow' &&
ssh mark@maximum "echo a803da2 > ~/fieldshow-data/DEPLOYED_SHA" &&
curl -fsS http://10.42.0.238:8876/api/health
```

With no parts backup, `parts/` keeps the PDFs `e786df3` engraved. For the same `intent.json` the parts are the same, so this is fine. If `intent.json` changed since, rebuild with the old image: run the `docker compose run ... fieldshow build` line from Update (without `docker compose build`) after the retag, then recreate.

Roll back an update made with the block above, from the tag `fieldshow:pre-<OLD>-to-<NEW>`. There is a single `pre-<OLD>-to-*` set per replaced SHA, and rollback always uses it. Its `<NEW>` is the first SHA attempted from `<OLD>`, which may differ from the SHA that finally went out:

```bash
ssh mark@maximum 'docker image ls fieldshow' &&   # pick the pre-<OLD>-to-<NEW> tag
OLD=<OLD> && B="$OLD-to-<NEW>" &&
ssh mark@maximum "cd ~/fieldshow-data && cp -p show.json.pre-$B show.json && rm -rf parts && cp -a parts.pre-$B parts" &&
ssh mark@maximum "cd ~/fieldshow && docker tag fieldshow:pre-$B \"\$(docker compose config --images fieldshow)\" && docker compose up -d --no-build --force-recreate fieldshow" &&
ssh mark@maximum "echo '$OLD' > ~/fieldshow-data/DEPLOYED_SHA" &&
U="used-$B-$(date +%Y%m%d%H%M%S)" &&
ssh mark@maximum "cd ~/fieldshow-data && mv show.json.pre-$B show.json.$U && mv parts.pre-$B parts.$U && docker tag fieldshow:pre-$B fieldshow:$U && docker rmi fieldshow:pre-$B >/dev/null" &&
curl -fsS http://10.42.0.238:8876/api/health
```

After restoring, the block retires the set: the tag and the `show.json`/`parts` backups are renamed `used-<OLD>-to-<NEW>-<timestamp>`. Update's lookup only matches `pre-<OLD>-to-*`, so the next Update from `<OLD>` takes a fresh set from the show as it is then, not this stale one. A rerun of this block after the retire stops at the first `cp` (the set is gone); the rollback has already happened. Delete old `used-*` tags and backups by hand when no longer wanted.

`docker compose config --images fieldshow` prints the image name Compose runs for the service, so the retag points that name at the old image. `--no-build` makes `up` run the image under that name exactly as tagged. If the name were missing it would fail rather than quietly build a fresh image from the new source on disk. Re-rsync the old SHA's export later, so the source on maximum matches the running image again. Rollback leaves the `pre-*` tag and backups in place, so it is safe to rerun.

Only for the older `fieldshow:pre-a803da2` fallback: images from before `a803da2` may not start against the `/data` override. Move the override out of `~/fieldshow` (inside it, the next `rsync --delete` would remove it), retag that image as above, and recreate. Do not run Update while the fallback is active; undo it first:

```bash
ssh mark@maximum '{ [ ! -e ~/fieldshow/compose.override.yaml ] || mv ~/fieldshow/compose.override.yaml ~/fieldshow-data/compose.override.yaml.off; } && cd ~/fieldshow && docker tag fieldshow:pre-a803da2 "$(docker compose config --images fieldshow)" && docker compose up -d --no-build --force-recreate fieldshow'
```

To undo it, put the override back, retag the `a803da2` image, recreate, and record `a803da2` as running:

```bash
ssh mark@maximum '{ [ ! -e ~/fieldshow-data/compose.override.yaml.off ] || mv ~/fieldshow-data/compose.override.yaml.off ~/fieldshow/compose.override.yaml; } && cd ~/fieldshow && docker tag fieldshow:pre-a803da2-to-e786df3 "$(docker compose config --images fieldshow)" && docker compose up -d --no-build --force-recreate fieldshow && echo a803da2 > ~/fieldshow-data/DEPLOYED_SHA' &&
curl -fsS http://10.42.0.238:8876/api/health
```

## Using it

From another lab machine: `http://10.42.0.238:8876/`.

Mount the whole directory that holds `show.json`, `parts/` and `images/`, not the JSON file alone. Mounting only the JSON file leaves every part marked unavailable, because the PDFs are files beside it.

The intent lives at `~/fieldshow-data/intent.json` on `maximum`. The first-time setup above mounts that directory at `/data`.

LilyPond is in the image. Build the show and its parts with the same image, then restart the service:

```bash
ssh mark@maximum 'cd ~/fieldshow && docker compose run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp fieldshow \
  fieldshow build /data/intent.json -o /data/show.json && docker compose up -d --no-build --force-recreate fieldshow'
curl -fsS http://10.42.0.238:8876/api/part-pdf/trumpet -o /dev/null -w '%{http_code} %{content_type}\n'
```

`fieldshow serve` reads the show JSON once at startup, so `--force-recreate` is what makes the page see the new build. Plain `up -d` leaves the old container and its old JSON running when the config is unchanged.

Expect `200 application/pdf`. A `404` means `parts/` is not beside the mounted `show.json` or the build printed `PDF parts unavailable` on stderr.

Stop: `docker compose down`. This does not remove the image.

### Field picture

`fieldshow build` rebuilds `show.json` from `intent.json`, so every rebuild (Update, or the build above) sets `field_image` to whatever `intent.json` says. Importing into `show.json` alone is lost at the next build: `images/field.<ext>` stays on disk but `/api/field-image` returns 404. The durable way is to import into `intent.json`, then build. `import-image` takes any show or intent JSON, writes `images/field.<ext>` beside its `-o` file and sets `field_image` to `images/field.<ext>`, which is the marker `intent.json` accepts.

Copy the picture into `~/fieldshow-data` first (the container only sees `/data`), import it into the intent, rebuild, recreate, and remove the copied source:

```bash
scp field.png mark@maximum:fieldshow-data/field-src.png &&
ssh mark@maximum 'cd ~/fieldshow && docker compose run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp fieldshow \
  fieldshow import-image /data/intent.json /data/field-src.png -o /data/intent.json && \
  docker compose run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp fieldshow fieldshow build /data/intent.json -o /data/show.json && \
  docker compose up -d --no-build --force-recreate fieldshow && rm ~/fieldshow-data/field-src.png' &&
curl -fsS http://10.42.0.238:8876/api/field-image -o /dev/null -w '%{http_code} %{content_type}\n'
```

Expect `200 image/png`. To set it by hand instead, put the file at `~/fieldshow-data/images/field.png` and set `"field_image": "images/field.png"` in `~/fieldshow-data/intent.json`, then rebuild. The alternative, `import-image /data/show.json ... -o /data/show.json` after each build, works until the next build.
