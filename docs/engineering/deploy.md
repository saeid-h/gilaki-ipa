# Deploy on 1404kingstreet.com

| What | Value |
|---|---|
| Public API | `https://1404kingstreet.com/gilaki-api` |
| Public app | `https://1404kingstreet.com/gilaki-app` |
| Internal process | `127.0.0.1:18741` |
| Host | Linux. Clone the GitHub repo; do not copy files by hand |

No API key in v1. Nginx terminates TLS with the certificate already used for the domain. MIT license.

## Start the API (required path)

Python packages live **only** in repo-root `.venv/` (gitignored). Never `sudo pip` or the system Python.

```bash
git clone https://github.com/saeid-h/gilaki-ipa.git
cd gilaki-ipa
# once: sudo apt install ffmpeg python3-venv   # OS packages, not pip
./scripts/start-server.sh
```

The script creates `.venv` at the **repository root** if needed, installs `api/requirements.txt` into it, and runs uvicorn on `127.0.0.1:18741`.

Optional systemd: `deploy/gilaki-api.service` should start that same script so the process survives reboot. Clone path is yours; `/opt/gilaki-ipa` is only an example.

## Nginx

Add this to the existing HTTPS server block for `1404kingstreet.com`. Point `alias` at **this clone’s** `web/` directory. Full snippet: `deploy/nginx-gilaki.conf`.

```nginx
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

location /gilaki-app/ {
    alias /opt/gilaki-ipa/web/;
}
```

The trailing slash on `proxy_pass` strips `/gilaki-api`, so FastAPI still sees `/health` and `/v1/recognize`.

Then:

```bash
sudo nginx -t && sudo systemctl reload nginx
curl -sS https://1404kingstreet.com/gilaki-api/health
```

Expected: `{"ok": true, "status": "up", ...}`

## Firewall

Do not open `18741` to the internet. Only 443 (already open) should reach clients.

## Client base URL

Web and Android default API base:

```
https://1404kingstreet.com/gilaki-api
```

No trailing slash. Join paths as `base + "/v1/recognize"`.

If the domain is not renewed later, change the default in the next app version. Users can already override it in Settings.
