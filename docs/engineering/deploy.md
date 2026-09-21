# Deploy on 1404kingstreet.com

| What | Value |
|---|---|
| Public API | `https://1404kingstreet.com/gilaki-api` |
| Public app | `https://1404kingstreet.com/gilaki-app` |
| Internal process | `127.0.0.1:18741` |
| Host | Linux. Clone the GitHub repo; do not copy files by hand |

No API key in v1. TLS is whatever already terminates **443** on this host. On vm6506 that is **Caddy in Docker** (`real-estate-investment-caddy-1`), not Nginx. Do not install Nginx on this box; it would fight Caddy for 443.

## Start the API (required path)

Python packages live **only** in repo-root `.venv/` (gitignored). Never `sudo pip` or the system Python.

```bash
git clone https://github.com/saeid-h/gilaki-ipa.git
cd gilaki-ipa
# once: sudo apt install ffmpeg python3-venv   # OS packages, not pip
./scripts/start-server.sh
```

The script creates `.venv` at the **repository root** if needed, installs `api/requirements.txt` into it, and runs uvicorn on `127.0.0.1:18741`. If `api/.env` has `ASR_BACKEND=allosaurus`, it also installs `api/requirements-allosaurus.txt` (GPL, server-only).

`ffmpeg` must be on PATH (`apt install ffmpeg` / `brew install ffmpeg`). Uploads are converted to 16 kHz mono WAV in a temp file that is always deleted. Missing ffmpeg → 501 `backend_unavailable`; unreadable audio → 422 `invalid_audio`; longer than 60 s → 422 `audio_too_long`.

Optional systemd: `deploy/gilaki-api.service` should start that same script so the process survives reboot. Clone path is yours; `/opt/gilaki-ipa` is only an example.

## Allosaurus (this 1 GB host)

Keep `ASR_BACKEND=mock` for Playwright and local UI work. On the public VM set `ASR_BACKEND=allosaurus` in `api/.env`.

This box has ~1 GB RAM and no swap. Add a 2 GB swap file **before** `pip install allosaurus` / first model load, or the process will OOM and take the other site down with it.

Install **CPU** torch (`pip install torch --index-url https://download.pytorch.org/whl/cpu`) then `api/requirements-allosaurus.txt`. A default torch wheel is CUDA and ~550 MB. `python3.13-dev` is needed to build `editdistance`. `ffmpeg` is required (`apt install ffmpeg`).

First `read_recognizer()` downloads weights (outbound HTTPS, no Hugging Face token). Mock stays in the same binary: change the env var and restart.

Leave `ALLOSAURUS_LANG=glk` (or `ipa`) so decoding uses the Gilaki inventory file. `ALLOSAURUS_LANG=all` restores the ~230-phone dump and the transcript will jump between similar world phones.

## Reverse proxy (this host: Caddy in Docker)

Uvicorn stays on `127.0.0.1:18741`. Port 443 is `real-estate-investment-caddy-1`. A bridge-network Caddy cannot reach that loopback bind (`host.docker.internal` is the docker0 gateway, not `127.0.0.1`, and UFW drops it). On this VM Caddy runs with **`network_mode: host`** so `reverse_proxy 127.0.0.1:18741` is the host uvicorn. The analyzer backend is published on host `8000`, so `/api/*` and `/health` use `127.0.0.1:8000` as well.

1. Find the compose project (do not run `docker compose` from `/root`):

```bash
docker inspect real-estate-investment-caddy-1 \
  --format '{{index .Config.Labels "com.docker.compose.project.working_dir"}}'
```

`cd` into that directory. `docker compose up -d caddy` only works there.

2. In that project's `docker-compose.yml`, on the **caddy** service: use `network_mode: host` (drop the `ports:` mapping; it is incompatible with host network), persist `/data` and `/config` so Let's Encrypt certs survive recreates, and mount the Gilaki web dir:

```yaml
caddy:
  image: caddy:2
  network_mode: host
  environment:
    - DOMAIN=${DOMAIN:-example.com}
  volumes:
    - ./caddy/Caddyfile:/etc/caddy/Caddyfile:ro
    - ./frontend/dist:/srv/frontend:ro
    - /root/gilaki-ipa/web:/srv/gilaki-web:ro
    - ./caddy-data:/data
    - ./caddy-config:/config
  depends_on:
    - backend
  restart: unless-stopped
```

(Adjust the web bind if the clone is not `/root/gilaki-ipa`.)

3. Inside the existing `1404kingstreet.com` site block, **before** the SPA catch-all, paste [`deploy/caddy-gilaki.Caddyfile`](../../deploy/caddy-gilaki.Caddyfile).

4. Reload Caddy from that compose directory:

```bash
docker compose up -d caddy
curl -sS https://1404kingstreet.com/gilaki-api/health
```

Expected JSON `{"ok": true, "status": "up", ...}`, not the Investment Property Analyzer HTML.

A host Nginx snippet still lives in `deploy/nginx-gilaki.conf` for machines that actually run Nginx. This server does not.

## Nginx (only if 443 is host Nginx, not this VM)

Add this to the existing HTTPS server block for `1404kingstreet.com` (the same `server { }` as the other app, **not** a new site). Prefix locations must sit alongside `location /` — Nginx will prefer `/gilaki-api/` over the catch-all SPA.

`/gilaki-api` with **no trailing slash** does not match `location /gilaki-api/`. Without the exact-match redirect, that URL is served by the other app on this host. Full snippet: `deploy/nginx-gilaki.conf`.

```nginx
location = /gilaki-api {
    return 301 /gilaki-api/;
}

location /gilaki-api/ {
    proxy_pass http://127.0.0.1:18741/;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    client_max_body_size 15m;
    proxy_read_timeout 120s;
}

location = /gilaki-app {
    return 301 /gilaki-app/;
}

location /gilaki-app/ {
    alias /opt/gilaki-ipa/web/;
}
```

The trailing slash on `proxy_pass` strips `/gilaki-api`, so FastAPI still sees `/health` and `/v1/recognize`.

Then:

```bash
sudo nginx -t && sudo systemctl reload nginx
curl -sSI https://1404kingstreet.com/gilaki-api
curl -sS https://1404kingstreet.com/gilaki-api/health
```

The first should 301 to `/gilaki-api/`. The second should be `{"ok": true, "status": "up", ...}` — **not** the Investment Property Analyzer HTML.

## Firewall

Do not open `18741` to the internet. Only 443 (already open) should reach clients.

## Client base URL

Web and Android default API base:

```
https://1404kingstreet.com/gilaki-api
```

No trailing slash. Join paths as `base + "/v1/recognize"`.

If the domain is not renewed later, change the default in the next app version. Users can already override it in Settings.
