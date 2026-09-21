# Gilaki IPA

Online transcriber for Gilaki (`glk`): speech → IPA → a user-chosen script.

- **API** (`api/`): phone recognition, preset maps, phonology.
- **Web** (`web/`): static client at `https://1404kingstreet.com/gilaki-app`.
- **Android** (`android/`, later): `com.kingstreet.gilaki`.

Audio is processed in memory on the server and **not stored**. Custom maps stay on the device.

Master plan: [`docs/product/plan.md`](docs/product/plan.md).  
How to add or update docs: [`docs/README.md`](docs/README.md).

## URLs

| What | Value |
|---|---|
| Public API | `https://1404kingstreet.com/gilaki-api` |
| Public app | `https://1404kingstreet.com/gilaki-app` |
| Local API | `http://127.0.0.1:18741` |

Clients store the API base **without** a trailing slash. No API key in v1.

## Repo layout

```
gilaki-ipa/
  api/                 FastAPI service
  schemas/             JSON Schema + preset maps
  web/                 Static web client
  android/             Android app (later)
  docs/                Plan, API, deploy
  deploy/              Nginx + systemd drafts
  .cursor/rules/       Rules for Cursor Agent
```

## Quick start (API)

Use a **project venv only** (repo-root `.venv/`, gitignored). Never install into the system Python.

On Linux (same path as the server):

```bash
./scripts/start-server.sh
```

Equivalent by hand (venv still required, still at repo root):

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r api/requirements.txt
cp api/.env.example api/.env
cd api && uvicorn app.main:app --host 127.0.0.1 --port 18741 --reload
```

Open `http://127.0.0.1:18741/docs`. Default `ASR_BACKEND=mock`.

Web client (zero-build): serve `web/` and point Settings at the local API.

```bash
python3 -m http.server 4173 --bind 127.0.0.1 --directory web
# in another shell: ./scripts/start-server.sh
# open http://127.0.0.1:4173 and set API base to http://127.0.0.1:18741
cd web && npm test && npx playwright test
```

## Privacy split

| Data | Where it lives |
|---|---|
| Preset maps (Varg, Latin, lossy Persian, …) | Server |
| Gilaki phone inventory | Server |
| ASR model weights | Server |
| Custom maps | Client only |
| Audio files | Client only |
| Request audio | RAM (plus a short-lived ffmpeg temp file that is deleted) |

## Status

Plan frozen. Implementation is one phase per chat. See `docs/product/plan.md`.
