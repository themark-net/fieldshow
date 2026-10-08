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

The container serves the sample fanfare until a show file is bind-mounted. To serve a built show, mount it at `/data/show.json` and set `FIELDSHOW_SHOW=/data/show.json`.

Update with the same rsync, then `docker compose up -d --build` again.

Stop: `docker compose down`. This does not remove the image.
