# Deploy on maximum

Host: `maximum`, `10.42.0.238`, user `mark`. Docker is already installed. The service listens on port 8876.

`maximum` does not have the `githu` GitHub key, so `git clone` there fails. From nimo:

```bash
rsync -az --delete --exclude .venv --exclude .git --exclude .project-map \
  ~/DEVELOP/fieldshow/ maximum:fieldshow/
ssh maximum 'cd ~/fieldshow && docker compose up -d --build'
curl -fsS http://10.42.0.238:8876/api/health
```

From another lab machine: `http://10.42.0.238:8876/`.

The container serves the sample fanfare until a show directory is bind-mounted. Mount the whole directory that holds `show.json` and `parts/`, not the JSON file alone:

```bash
docker run --rm -p 8876:8876 \
  -v /path/showdir:/data \
  -e FIELDSHOW_SHOW=/data/show.json \
  fieldshow:t0005
```

LilyPond is in the image. Build the parts there, then serve that same directory:

```bash
docker run --rm -v /path/showdir:/data -e HOME=/tmp --user "$(id -u):$(id -g)" \
  fieldshow:t0005 \
  fieldshow build /data/show.json -o /data/show.json
```

Mounting only the JSON file leaves every part marked unavailable, because the PDFs are files beside it.

Update with the same rsync, then `docker compose up -d --build` again.

Stop: `docker compose down`. This does not remove the image.
