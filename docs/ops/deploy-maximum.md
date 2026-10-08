# Deploy on maximum

Host: `maximum`, `10.42.0.238`, user `mark`. Docker is already installed. The service listens on port 8876.

```bash
git clone git@github.com:themark-net/fieldshow.git
cd fieldshow
docker compose up -d --build
curl -fsS http://127.0.0.1:8876/api/health
```

From another lab machine: `http://10.42.0.238:8876/`.

The container serves the sample fanfare until a show file is bind-mounted. To serve a built show, mount it at `/data/show.json` and set `FIELDSHOW_SHOW=/data/show.json`.

Update:

```bash
git pull
docker compose up -d --build
```

Stop: `docker compose down`. This does not remove the image.
