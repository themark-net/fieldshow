# Deploy on maximum

Host: `maximum`, `10.42.0.238`, user `mark`. Docker is already installed. The service listens on port 8876.

`maximum` does not have the `githu` GitHub key, so `git clone` there fails. From nimo:

```bash
rsync -az --delete --exclude .venv --exclude .git --exclude .project-map --exclude /tmp --exclude /compose.override.yaml \
  ~/DEVELOP/fieldshow/ maximum:fieldshow/
ssh maximum 'cd ~/fieldshow && docker compose up -d --build'
curl -fsS http://10.42.0.238:8876/api/health
```

From another lab machine: `http://10.42.0.238:8876/`.

The container serves the sample fanfare until a show directory is bind-mounted. Mount the whole directory that holds `show.json` and `parts/`, not the JSON file alone. Mounting only the JSON file leaves every part marked unavailable, because the PDFs are files beside it.

On `maximum`, put the intent at `~/fieldshow-data/intent.json` and add `~/fieldshow/compose.override.yaml` (not in git; the rsync above excludes it, so `--delete` keeps it):

```yaml
services:
  fieldshow:
    volumes:
      - /home/mark/fieldshow-data:/data
    environment:
      FIELDSHOW_SHOW: /data/show.json
```

LilyPond is in the image. Build the show and its parts with the same image, then restart the service:

```bash
ssh maximum 'cd ~/fieldshow && docker compose run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp fieldshow \
  fieldshow build /data/intent.json -o /data/show.json && docker compose up -d --force-recreate fieldshow'
curl -fsS http://10.42.0.238:8876/api/part-pdf/trumpet -o /dev/null -w '%{http_code} %{content_type}\n'
```

`fieldshow serve` reads the show JSON once at startup, so `--force-recreate` is what makes the page see the new build. Plain `up -d` leaves the old container and its old JSON running when the config is unchanged.

Expect `200 application/pdf`. A `404` means `parts/` is not beside the mounted `show.json` or the build printed `PDF parts unavailable` on stderr.

Update with the same rsync, then `docker compose up -d --build` again.

Stop: `docker compose down`. This does not remove the image.
