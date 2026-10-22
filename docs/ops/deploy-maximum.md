# Deploy on maximum

Host: `maximum`, `10.42.0.238`, user `mark`. Docker is already installed. The service listens on port 8876.

`maximum` does not have the `githu` GitHub key, so `git clone` there fails. Deploy from nimo. Copy a clean export of the target commit, never a working tree: a working tree carries `tmp/` worktrees, mutant scratch and local edits.

## Clean export (nimo)

```bash
SHA=<target sha>
git -C ~/DEVELOP/fieldshow fetch origin
rm -rf /tmp/fieldshow-deploy-$SHA && mkdir /tmp/fieldshow-deploy-$SHA
git -C ~/DEVELOP/fieldshow archive "$SHA" | tar -x -C /tmp/fieldshow-deploy-$SHA
```

## First-time setup (maximum)

Do this once, before the first `up`.

```bash
ssh maximum 'mkdir -p ~/fieldshow /home/mark/fieldshow-data && cat > ~/fieldshow/compose.override.yaml' <<'YAML'
services:
  fieldshow:
    volumes:
      - /home/mark/fieldshow-data:/data
    environment:
      FIELDSHOW_SHOW: /data/show.json
YAML
rsync -az --delete --exclude /compose.override.yaml /tmp/fieldshow-deploy-$SHA/ maximum:fieldshow/
ssh maximum 'cp ~/fieldshow/examples/fanfare.json ~/fieldshow-data/intent.json'
```

`compose.override.yaml` is not in git. `--exclude /compose.override.yaml` keeps `--delete` from removing it. `--delete` does remove every other untracked leftover in `~/fieldshow` on maximum, so keep nothing else there. Then seed `show.json` from the example and start the service:

```bash
ssh maximum 'cd ~/fieldshow && docker compose build fieldshow && docker compose run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp fieldshow \
  fieldshow build /data/intent.json -o /data/show.json && docker compose up -d --force-recreate fieldshow'
curl -fsS http://10.42.0.238:8876/api/health
```

## Update

Before you replace anything, tag the running image and back up the built show, so there is something to roll back to. Both use the replaced commit's short SHA (`pre-<sha>`):

```bash
OLD=<short sha now running on maximum>
ssh maximum "cd ~/fieldshow && docker tag \$(docker compose images -q fieldshow) fieldshow:pre-$OLD"
ssh maximum "cd ~/fieldshow-data && cp -p show.json show.json.pre-$OLD && rm -rf parts.pre-$OLD && cp -a parts parts.pre-$OLD"
rsync -az --delete --exclude /compose.override.yaml /tmp/fieldshow-deploy-$SHA/ maximum:fieldshow/
ssh maximum 'cd ~/fieldshow && docker compose build fieldshow && docker compose run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp fieldshow fieldshow build /data/intent.json -o /data/show.json && docker compose up -d --no-build --force-recreate fieldshow'
curl -fsS http://10.42.0.238:8876/api/health
```

`fieldshow build` overwrites `show.json` and `parts/`, which is why the backup comes first. The update reruns `fieldshow build` because `serve` only reads `/data/show.json`. Without the build, the new image serves the old `show.json` and the old part PDFs. The old container keeps serving until the final `up -d --no-build --force-recreate fieldshow`. The build and the `run --rm` do not touch it.

If `docker compose build` fails while pulling from Docker Hub with `network is unreachable`, maximum's IPv6 route is flaky. Rerun the same command. The old container is still serving.

## Rollback

The current rollback image is `fieldshow:pre-a803da2` (`sha256:0f631c29aa48...`). Sysadmin tagged it, and it is not `fieldshow-fieldshow:pre-<stamp>`. New tags follow `fieldshow:pre-<replaced short SHA>`, as in Update above.

Restore the show built by the old image as well as the image itself. The new build has already overwritten `/data/show.json` and `parts/`:

```bash
OLD=<sha of the pre-* tag>   # a803da2 today
ssh maximum 'docker image ls fieldshow'   # pick the pre-* tag
ssh maximum "cd ~/fieldshow-data && cp -p show.json.pre-$OLD show.json && rm -rf parts && cp -a parts.pre-$OLD parts"
ssh maximum "cd ~/fieldshow && docker tag fieldshow:pre-$OLD \"\$(docker compose config --images fieldshow)\" && docker compose up -d --no-build --force-recreate fieldshow"
curl -fsS http://10.42.0.238:8876/api/health
```

`docker compose config --images fieldshow` prints the image name Compose runs for the service, so the retag points that name at the old image. `--no-build` makes `up` run the image under that name exactly as tagged. If the name were missing it would fail rather than quietly build a fresh image from the new source on disk. The `show.json.pre-a803da2` backup exists only if it was taken before that update. If there is none, rerun the old image's `fieldshow build` (the `docker compose run` line in Update, without `docker compose build`) after the retag. Re-rsync the old SHA's export later, so the source on maximum matches the running image again.

Images from before `a803da2` cannot serve part PDFs, and they may not start against the `/data` override. For a full return to the old setup, first move the override aside (`mv ~/fieldshow/compose.override.yaml ~/fieldshow/compose.override.yaml.off`), then recreate.

## Using it

From another lab machine: `http://10.42.0.238:8876/`.

Mount the whole directory that holds `show.json`, `parts/` and `images/`, not the JSON file alone. Mounting only the JSON file leaves every part marked unavailable, because the PDFs are files beside it.

The intent lives at `~/fieldshow-data/intent.json` on `maximum`. The first-time setup above mounts that directory at `/data`.

LilyPond is in the image. Build the show and its parts with the same image, then restart the service:

```bash
ssh maximum 'cd ~/fieldshow && docker compose run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp fieldshow \
  fieldshow build /data/intent.json -o /data/show.json && docker compose up -d --force-recreate fieldshow'
curl -fsS http://10.42.0.238:8876/api/part-pdf/trumpet -o /dev/null -w '%{http_code} %{content_type}\n'
```

`fieldshow serve` reads the show JSON once at startup, so `--force-recreate` is what makes the page see the new build. Plain `up -d` leaves the old container and its old JSON running when the config is unchanged.

Expect `200 application/pdf`. A `404` means `parts/` is not beside the mounted `show.json` or the build printed `PDF parts unavailable` on stderr.

Stop: `docker compose down`. This does not remove the image.

A field picture goes in the same directory. Copy it into `~/fieldshow-data` first (the container only sees `/data`), import it with the image, then recreate the service:

```bash
scp field.png maximum:fieldshow-data/field-src.png
ssh maximum 'cd ~/fieldshow && docker compose run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp fieldshow \
  fieldshow import-image /data/show.json /data/field-src.png -o /data/show.json && docker compose up -d --no-build --force-recreate fieldshow'
curl -fsS http://10.42.0.238:8876/api/field-image -o /dev/null -w '%{http_code} %{content_type}\n'
```

`import-image` writes `/data/images/field.<ext>` and stores `images/field.<ext>`. Expect `200 image/png`.
