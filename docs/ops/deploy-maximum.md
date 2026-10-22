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

`compose.override.yaml` is not in git. `--exclude /compose.override.yaml` keeps `--delete` from removing it. Then seed `show.json` from the example and start the service:

```bash
ssh maximum 'cd ~/fieldshow && docker compose build && docker compose run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp fieldshow \
  fieldshow build /data/intent.json -o /data/show.json && docker compose up -d'
curl -fsS http://10.42.0.238:8876/api/health
```

## Update

Tag the running image before you replace it, so there is something to roll back to:

```bash
ssh maximum 'docker tag fieldshow-fieldshow:latest fieldshow-fieldshow:pre-$(date +%Y%m%d-%H%M)'
rsync -az --delete --exclude /compose.override.yaml /tmp/fieldshow-deploy-$SHA/ maximum:fieldshow/
ssh maximum 'cd ~/fieldshow && docker compose up -d --build --force-recreate'
curl -fsS http://10.42.0.238:8876/api/health
```

`fieldshow-fieldshow` is the name Compose gives the image for project `fieldshow` and service `fieldshow`. Run `docker compose images` to check it.

## Rollback

```bash
ssh maximum 'docker image ls fieldshow-fieldshow'   # pick the pre-* tag
ssh maximum 'cd ~/fieldshow && docker tag fieldshow-fieldshow:pre-<stamp> fieldshow-fieldshow:latest && docker compose up -d --no-build --force-recreate'
curl -fsS http://10.42.0.238:8876/api/health
```

`--no-build` matters: without it Compose rebuilds from the new source and the rollback is undone. Re-rsync the old SHA's export later so the source on maximum matches the running image again.

## Using it

From another lab machine: `http://10.42.0.238:8876/`.

The container serves the sample fanfare until a show directory is bind-mounted. Mount the whole directory that holds `show.json`, `parts/` and `images/`, not the JSON file alone. Mounting only the JSON file leaves every part marked unavailable, because the PDFs are files beside it.

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

A field picture goes in the same directory: `fieldshow import-image /data/show.json <img> -o /data/show.json` writes `/data/images/field.<ext>`.
