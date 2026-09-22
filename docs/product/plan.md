# Gilaki IPA — Master Plan

Source of truth for Cursor Plan mode. Implement only after this document is accepted. One implementation phase per chat.

Status: plan frozen 2026-09-21. Phase 3 public HTTPS is live (`/gilaki-api`, `/gilaki-app` on Caddy).

---

## 1. Product

### 1.1 What it is

An **online Gilaki transcriber**. The user records or picks audio and gets written Gilaki in a chosen script.

Gilaki (`glk`) has **no single standard orthography**. The product therefore does **not** jump from audio to letters in one model. It does:

1. Audio → **IPA** (broad phonemic transcription) — the model, approximate
2. IPA → user-selected **transcript map** — deterministic: same IPA + same map = same text every time
3. Maps may be a known script (Perso-Arabic / Farsi-style, Latin, English-approximate, Cyrillic later) or a **user-defined custom map**

Positioning: a transcriber for Gilaki speech, not “Gilaki Whisper,” and not an in-session IPA editor.

v1 UI:

- **Main result:** mapped transcript
- **IPA:** hidden by default; optional control to show phones
- Users do **not** edit IPA during a session. Wrong phones → record again
- Changing the active map **rewrites locally** from the last IPA (no re-upload)
- Custom map editor lives in Settings / Maps, not on the live result as the main action

Quality loop (correct IPA, export `wav + ipa.txt`) is Phase 7, after v1 works.

### 1.2 Who it is for

- Gilaki speakers who want to write speech in a chosen script
- Writers using Varg / Gileva-style Perso-Arabic or Latin
- People who only read ordinary Persian letters (lossy map, labelled)
- Linguists who opt in to IPA
- The operator (you), who wants a growing corrected IPA corpus later — collected on devices, not on the API disk

### 1.3 Non-goals for v1

- User accounts, login, OAuth
- API keys in the apps
- Storing user audio on the server
- Storing custom maps on the server
- Word segmentation / dictionary lookup
- Translation
- TTS
- Automatic dialect classification (manual tag is enough)
- Paid third-party ASR (OpenAI / Google / Azure speech APIs)
- Play Store release hardening beyond a working debug/release APK
- In-session IPA editing
- Showing Allosaurus timestamps in the UI
- Cyrillic preset (schema allows `Cyrl`; do not ship one until a later revision)

---

## 2. Why this design

### 2.1 Language facts

- Northwestern Iranian / Caspian language, close to Mazandarani
- ISO 639-3: `glk`
- Main dialects: Western (e.g. Rasht), Eastern, Galeshi / Deylami
- Consonants ≈ Persian; **vowels differ**. Schwa `/ə/` is frequent and must not be silently dropped in scholarly maps
- Writing in the wild: proposed Gilaki Perso-Arabic (Payandeh Langarudi → Gileva → Varg), Latin schemes, academic Iranian transcription, ordinary Persian spelling

### 2.2 Why not grapheme ASR first

DOLMA-NLP / Interspeech 2025 fine-tuned Whisper on a small Gilaki set (~5.4 h train). Gilaki was the hardest language; WER stayed around **89–93%**. Inconsistent Arabic-script labels are a major reason.

Conclusion: train or call **phone/IPA models**, then map. If grapheme ASR is added later, one model per orthography — never mix Varg + naive Persian + Latin labels in one dataset.

### 2.3 Research pieces available (reuse, do not depend)

- DOLMA-speech and `razhan/whisper-base-glk` — too weak as the core engine; optional later comparison
- PARME parallel sentences — useful for map design, not acoustics
- Published phonology (Rastorgueva *The Gilaki Language*, Wikipedia, Iranica)
- Allosaurus — first real IPA backend
- Wav2Vec2-IPA / PhoneticXeus / WhisperIPA — later benchmarks
- UH Kaipuleohone and religious/media audio — only if IPA’d by hand

v1 does **not** require buying any of these as a service. Weights run on your server.

---

## 3. Locked product / ops decisions

These are closed unless a later plan revision explicitly changes them.

| Decision | Value |
|---|---|
| Public API URL | `https://1404kingstreet.com/gilaki-api` |
| Public app URL | `https://1404kingstreet.com/gilaki-app` |
| Internal process bind | `127.0.0.1:18741` |
| Public TLS | Existing **443** terminator (this host: Caddy in Docker `real-estate-investment-caddy-1`, not Nginx) |
| Unique port on the internet | **No.** 18741 stays localhost only |
| Domain risk | Domain may not be renewed. Clients must have an editable API base URL. Next app version can change the default. |
| Auth / API key | **None in v1** (free service) |
| Accounts | None in v1 |
| Abuse controls | Max upload 12 MB, max duration 60 s, **in-memory** 30 requests / IP / 10 minutes |
| Android `applicationId` | `com.kingstreet.gilaki` |
| Default client flow | Server returns IPA; client applies map locally |
| Result hierarchy | Mapped text primary; IPA optional show |
| IPA editing in v1 | No |
| Audio persistence | Client only |
| Custom maps persistence | Client only |
| Preset maps | Server catalog, cacheable on client |
| Paid cloud ASR | Not used |
| First ASR backend | `mock` for UI work, then `allosaurus` on the server |
| IPA grain | Broad phonemic, not ultra-narrow phonetic |
| Web stack | Zero-build `web/index.html` |
| Visual system | **Caspian Paper** — `docs/product/design.md` (web + Android, same tokens) |
| UI chrome | English + Persian, toggle in Settings, **default English** |
| Default map | `varg-perso-arabic` |
| Repo license | MIT for this repo; Allosaurus stays a server-side GPL runtime, never in the APK |
| CI | GitHub Actions: pytest from Phase 1; Playwright from Phase 4 |
| Web tests | Playwright against mock + JS rewriter unit tests |
| Map editor | Raw JSON in Settings / Maps |
| Timestamps in v1 UI | No |
| GitHub | Public `https://github.com/saeid-h/gilaki-ipa` |
| Server OS | Linux. Operator clones the GitHub repo and runs `scripts/start-server.sh` |
| Python | Dedicated repo-root `.venv/` only (gitignored). Never system/global `pip` |
| Master plan path | `docs/product/plan.md` only (never repo root) |

---

## 4. Architecture

```
[Web https://1404kingstreet.com/gilaki-app]
[Android com.kingstreet.gilaki]
        │
        │  HTTPS  API base: https://1404kingstreet.com/gilaki-api
        └───────────────┬───────────────────┘
                        │
              Caddy :443  (Docker, network_mode: host)
              handle_path /gilaki-api/*  →  127.0.0.1:18741
              handle_path /gilaki-app/*  →  static files (web/)
                        │
              FastAPI (Uvicorn) 127.0.0.1:18741
                        │
         ┌──────────────┼─────────────────┐
         │              │                 │
   preset maps    Gilaki inventory    ASR backend
   (server)       (server)            mock | allosaurus
```

Same host, two paths: the browser origin is `https://1404kingstreet.com` for both, so CORS is that origin.

Path prefix: Caddy `handle_path /gilaki-api/*` strips the prefix (Nginx equivalent: `location /gilaki-api/` with `proxy_pass http://127.0.0.1:18741/;`). Bare `/gilaki-api` must 308/301 to `/gilaki-api/`, or the other site on this host will serve it. FastAPI routes stay `/health`, `/v1/recognize`, not `/gilaki-api/health`.

Clients store API base URL **without a trailing slash**:

```
https://1404kingstreet.com/gilaki-api
```

Request paths: `base + "/health"`, `base + "/v1/recognize"`.

Web users open `https://1404kingstreet.com/gilaki-app`. Android default API base is the `gilaki-api` URL.

### 4.1 Privacy split

| Data | Where |
|---|---|
| Model weights | Server disk |
| Standard / preset maps | Server disk; clients may cache |
| Gilaki phone inventory | Server |
| Request audio | RAM (+ short-lived temp wav deleted in `finally`). Never an `uploads/` library |
| Logs | request id, duration, byte size, IP or IP hash, status. Not the recording, not full IPA dumps of users if avoidable |
| Custom maps | `localStorage` (web), DataStore/Room (Android) |
| User audio files | App-private storage / user-chosen files |
| Corrections (future) | On device first; export folder the owner copies off-device |

Custom maps may be sent once as `map_json` on a recognize call if the client wants server-side rewrite. That JSON is request-scoped and **not saved**. Default is local rewrite.

### 4.2 Why no API key in v1

A key shipped inside a free public APK is extractable. It is not user identity.

v1 is open to anyone who can reach the HTTPS URL, protected only by size/rate limits. If abuse appears, a later version may add an invite code or key. That is a plan revision, not v1 work.

---

## 5. End-to-end pipeline

```
file or microphone
  → encode / upload over HTTPS
  → Nginx /gilaki-api/
  → FastAPI
  → ffmpeg: 16 kHz mono WAV in a NamedTemporaryFile
  → reject if duration > MAX_DURATION_SEC
  → ASR backend → phone list (IPA tokens)
  → optional alias normalize via gilaki_inventory.json
  → optional apply preset or inline map
  → JSON response
  → delete temp file
  → client shows mapped transcript (main)
  → client may toggle IPA
  → client may correct IPA on device and remap locally
  → client may export `wav` + `ipa.txt` locally (quality loop)
  → client may re-map locally when the user changes map
```

Word boundaries are **not** invented in v1. IPA is a space-separated phone string. Mapped text is a glyph string; users may copy it and add spaces by hand if they want word breaks.

ffmpeg failures:

- Missing ffmpeg binary → 501 `backend_unavailable`
- Corrupt or unreadable upload → 422 `invalid_audio`
- Video-with-audio containers (MediaRecorder webm) → extract audio track

---

## 6. Phonology (starting inventory)

File: `schemas/gilaki_inventory.json`  
Profile: `gilaki-western-broad`

Vowels: `i iː e ɛ ə a ä ɒ o u uː ü`

Consonants: `p b t d tʃ dʒ k g ʔ f v s z ʃ ʒ x ɣ h m n ŋ l r j`

Aliases (normalize incoming phones before mapping):

- `č` → `tʃ`, `ǰ` → `dʒ`, `š` → `ʃ`, `ž` → `ʒ`
- `χ` → `x`, `ʁ` → `ɣ`, `ɾ` → `r`
- `æ` → `ä`, `ɑ` → `ɒ`, `y` → `ü`

Notes:

- `x` covers `[x]~[χ]`; `ɣ` covers `[ɣ]~[ʁ]`; `r` covers `[r]~[ɾ]`
- Eastern / Galeshi may later be extra inventory profiles, not v1 blockers
- Dialect field on recognize: `western | eastern | galeshi | unspecified` (stored on the request only)

---

## 7. Transcript maps

### 7.1 Schema

File: `schemas/map.schema.json`

Required: `id`, `name`, `script`, `rules`

- `script`: `Arab | Latn | Cyrl | Grek | Zyyy`
- `direction`: `rtl | ltr`
- `lossy`: boolean
- `normalize`: `NFC` default
- `separator`: default `""`
- `unknown`: if omitted, keep the IPA symbol
- `rules[]`: `{ "ipa": "...", "out": "...", "note?": "..." }`

Rewrite algorithm: **longest IPA key first**. `tʃ` must win over `t` + `ʃ`.  
IPA input to the rewriter is a space-separated token string.

### 7.2 Presets on the server (v1)

| id | Name | Script | Lossy | Role |
|---|---|---|---|---|
| `varg-perso-arabic` | Varg-style Perso-Arabic | Arab RTL | no | Keep schwa as `ٚ` and extra vowel letters |
| `academic-latin` | Academic Latin | Latn LTR | no | `ə č ǰ š ž å` style |
| `lossy-persian` | Persian-compatible | Arab RTL | **yes** | Ordinary Persian letters; vowels collapse |
| `ipa` | IPA | phones LTR | no | Space-separated broad IPA (same as Show IPA, as the main card) |
| `english-approx` | English approximate | Latn LTR | yes | `sh zh kh gh` reading aid |

Cyrillic is allowed by the schema but **no official community standard**. Do not ship a Cyrillic preset until someone drafts one in a plan revision.

Varg-style map is an **approximation** for engineering, not a claim of orthographic authority. Keep the draft glyphs unless a native reader objects in a later revision.

### 7.3 Custom maps

Edited only on the client (raw JSON in v1). Same JSON shape. Never written to server disk.

---

## 8. API contract v1

Base (public): `https://1404kingstreet.com/gilaki-api`  
Base (local dev): `http://127.0.0.1:18741`

Success bodies include `"ok": true`.  
Errors: HTTP status + `{ "ok": false, "error": { "code": "...", "message": "..." } }`.

No `x-api-key` required. If server env `API_KEY` is empty, auth middleware is off.

### `GET /health`

```json
{ "ok": true, "status": "up", "backend": "mock", "version": "0.1.0" }
```

Public check: `https://1404kingstreet.com/gilaki-api/health`

### `GET /v1/phonology`

Returns `schemas/gilaki_inventory.json` wrapped as `{ "ok": true, "inventory": { ... } }`.

### `GET /v1/presets`

Summaries: id, name, script, direction, lossy, description.

### `GET /v1/presets/{id}`

Full map document.

### `POST /v1/recognize`

`multipart/form-data`

| Field | Required | Notes |
|---|---|---|
| `audio` | yes | wav, mp3, m4a, ogg, webm, flac |
| `preset_id` | no | apply this server preset |
| `map_json` | no | inline map; overrides preset; not stored |
| `return_mapped` | no | default true if a map is present |
| `dialect` | no | default `unspecified` |
| `timestamps` | no | default false; v1 UI ignores timestamps even if true |

Response includes `request_id`, `ipa` (space-separated), `phones[]`, optional `mapped_text`, `map_used`, `backend`, audio duration/sample rate, original filename. Audio bytes are discarded after the handler returns.

Limits:

- `MAX_UPLOAD_MB=12` → 413 `payload_too_large`
- `MAX_DURATION_SEC=60` → 422 `audio_too_long`
- Rate limit: **30 requests / IP / 10 minutes**, in-memory, single process → 429
- Empty file → 422 `empty_audio`

### `POST /v1/map`

JSON `{ "ipa": "...", "preset_id": "..." }` or `{ "ipa": "...", "map": { ... } }`.  
Lets tests rewrite without audio. Production clients should rewrite locally.

---

## 9. Clients

### 9.1 Shared behaviour

- Settings: **API base URL** (default `https://1404kingstreet.com/gilaki-api`). No API key field in v1. **UI language** toggle: English (default) or Persian; both string tables ship in v1.
- File pick + microphone
- Load preset list from server; cache locally
- Mapped text is the headline result; IPA behind an optional show
- First-launch / default preset: `varg-perso-arabic`
- RTL when the active map `direction` is `rtl`
- Show a lossy warning when `lossy: true`
- Custom map editor: raw JSON, persisted on device
- Changing map rewrites from last IPA locally
- Do not upload custom maps unless a clearly labelled option “apply this map on server for this request” is on
- If the domain dies, user pastes a new base URL; next release can change the default

### 9.2 Web

- Zero-build static page `web/index.html`, served at `/gilaki-app/`
- Mic via MediaRecorder; send the blob as the `audio` file part (webm/mp4/wav)
- Custom maps in `localStorage`
- Persist last API base URL in `localStorage`

### 9.3 Android

- Package / applicationId: **`com.kingstreet.gilaki`** (do not change later)
- Kotlin app, Retrofit/OkHttp
- Screens: Record, Result (mapped text + optional IPA), Maps, Settings
- Maps in DataStore (or Room if editor grows)
- Audio in app-private storage
- Production: HTTPS only (no cleartext)
- Debug cleartext only if someone tests raw LAN HTTP; production path is the domain
- Signing keystore is the operator’s responsibility; losing it means a new app id

### 9.4 Visual system (Caspian Paper)

Web and Android share **one** look: [`design.md`](design.md).

Inspired by the Stitch `DESIGN.md` format in [awesome-design-md](https://github.com/VoltAgent/awesome-design-md) (Notion-like cream reading surfaces, Mintlify’s single green, not a clone of those brands, not ElevenLabs dark).

- Cream paper canvas, **one** Caspian teal `#1A6B62` for record / selected map
- Mapped transcript is the largest type on a paper card
- IPA smaller, optional, never the hero
- Vazirmatn for UI + Arabic; Source Serif 4 for Latin maps; Charis SIL / Noto for IPA
- RTL follows the **active map**
- Lossy maps use clay, not danger red
- No dark mode in v1
- No design spec at repo root (lives at `docs/product/design.md`)

---

## 10. Server software

### 10.1 Stack

- Python 3.11+ **in a project venv at repo root** (`.venv/`, gitignored). Never install Gilaki deps into the system Python
- FastAPI + Uvicorn (installed only inside that venv)
- ffmpeg on PATH (OS package, e.g. `apt install ffmpeg` — not pip)
- pytest (in the venv)
- ASR: mock, then Allosaurus (`pip install allosaurus` **inside the venv**, GPL-3.0 — **run** on the server; do not embed inside the APK)
- Optional later: Wav2Vec2-IPA on the same `/v1/recognize` switch

### 10.2 Env

```
APP_VERSION=0.1.0
API_KEY=
ASR_BACKEND=mock
BIND_HOST=127.0.0.1
BIND_PORT=18741
MAX_UPLOAD_MB=12
MAX_DURATION_SEC=60
CORS_ORIGINS=https://1404kingstreet.com,http://127.0.0.1:18741,http://localhost:18741,http://127.0.0.1:4173,http://localhost:4173
PRESETS_DIR=../schemas/presets
INVENTORY_PATH=../schemas/gilaki_inventory.json
ALLOSAURUS_LANG=ipa
```

`ALLOSAURUS_LANG=ipa` (the default) returns the model's own phones unchanged. The IPA line is what was heard. Orthographic maps fold inventory aliases (`t͡ʃ` → `tʃ`) before their writing rules. The IPA preset does not fold. `ALLOSAURUS_LANG=glk` forces `schemas/gilaki_inventory.json` inside the recognizer and rewrites sounds outside that set.

`API_KEY` stays empty in v1. Local API listen: `127.0.0.1:18741` (not 8080, not `0.0.0.0` on the public host).

### 10.3 Deploy (Linux)

Operator machine: clone this repo, then start with the repo script. Do not `pip install` into the global interpreter.

```bash
git clone https://github.com/saeid-h/gilaki-ipa.git
cd gilaki-ipa
./scripts/start-server.sh
```

`scripts/start-server.sh` (bash, Linux) must:

1. Require `python3` ≥ 3.11 on PATH (the interpreter only; packages never go there)
2. Create repo-root `.venv` with `python3 -m venv` if it does not exist
3. Install/upgrade deps with `.venv/bin/pip install -r api/requirements.txt` only
4. Copy `api/.env.example` → `api/.env` if `.env` is missing
5. Exec `.venv/bin/uvicorn` (working directory `api/`) bound to `127.0.0.1:18741`

Idempotent: a second run reuses the existing venv. Never `sudo pip`, never `--break-system-packages` against system Python.

ffmpeg is an OS package (`apt install ffmpeg`), not a venv package.

Reverse proxy: this host uses Caddy (`deploy/caddy-gilaki.Caddyfile`). Nginx snippet: `deploy/nginx-gilaki.conf` (other machines).
Optional systemd: `deploy/gilaki-api.service` should `ExecStart=` that same script (or the venv uvicorn) so reboot survives. Path `/opt/gilaki-ipa` is only a suggestion; clone wherever you like and point the static alias at `web/`.

Checks after deploy:

```bash
curl -sS https://1404kingstreet.com/gilaki-api/health
```

Firewall: 443 open (already). **18741 closed** to WAN.

Hardware: CPU is enough for Allosaurus on short clips. No GPU required for v1. No extra paid service.

Allosaurus first-run downloads weights into the venv/user cache (needs outbound HTTPS once). No Hugging Face token required for that backend.

---

## 11. Implementation phases

Implement in this order. Do not start Android before the API contract is stable. Do not start Allosaurus before a client can talk to mock.

### Phase 0 — plan freeze (this file)

Done when this document matches the locked table in §3 and sibling docs do not contradict it.

**Tests:** none. This phase is documentation.

### Phase 1 — API + mock + limits

- FastAPI routes as in §8
- Mock backend returns a fixed Gilaki-like phone string so UI can be built
- Rewriter + unit tests
- Size + in-memory rate limits
- Bind 127.0.0.1:18741
- `scripts/start-server.sh` creates/uses repo-root `.venv` and starts uvicorn (no global pip)
- No disk writes of audio

**Done when:** `pytest` in `api/` is green. See §12.1.

### Phase 2 — ffmpeg

- Any allowed upload → 16 kHz mono
- Duration guard
- Temp file always deleted
- Error codes as in §5

**Done when:** §12.2 pytest is green (skip ffmpeg cases only if the binary is missing and the skip is explicit).

### Phase 3 — public HTTPS paths

- Operator clones `https://github.com/saeid-h/gilaki-ipa` on the Linux host and runs `./scripts/start-server.sh`
- Merge [`deploy/caddy-gilaki.Caddyfile`](../../deploy/caddy-gilaki.Caddyfile) into the existing `1404kingstreet.com` Caddy site (this host). Hosts that terminate TLS with Nginx use [`deploy/nginx-gilaki.conf`](../../deploy/nginx-gilaki.conf) instead
- Optional systemd calling the same script
- `curl https://1404kingstreet.com/gilaki-api/health` succeeds
- Static app reachable at `https://1404kingstreet.com/gilaki-app/`

**Done when:** §12.3 smoke commands succeed.

### Phase 4 — web client

- Settings URL, file, mic, presets, mapped text, optional IPA, local custom map JSON
- Shared rewriter in a small `web/` JS module (not inline-only) so unit tests can import it
- UI follows `docs/product/design.md` (Caspian Paper)

**Done when:** JS rewriter tests + Playwright against mock are green, and the UI checklist in §12.4 is ticked.

### Phase 5 — Android client

- Same features, applicationId locked
- Same rewriter cases as unit tests in Kotlin
- Material 3 roles mapped to Caspian Paper tokens in `docs/product/design.md` (no default purple)

**Done when:** Gradle unit tests green, `applicationId` is `com.kingstreet.gilaki`, §12.5 checklist ticked. (No Espresso in v1 unless a later revision adds it.)

### Phase 6 — Allosaurus

- `ASR_BACKEND=allosaurus`
- Inventory alias normalize
- Mock remains available for offline UI work

**Done when:** §12.6 pytest green; mock tests from Phase 1 still pass with `ASR_BACKEND=mock`.

### Phase 7 — quality loop (after v1 works)

- On-device “correct this IPA”
- Export `wav + ipa.txt` locally
- Fine-tune / adapt offline
- Still no training corpus uploaded to the API by default

**Done when:** export folder shape is tested; PER scored on a local 20–50 clip set (not WER).

---

## 12. Test plan (per phase)

A phase is not done because the feature “looks like it works.” It is done when that phase’s tests below pass. Later phases must not regress earlier pytest.

Shared rewriter cases (Python, JS, and Kotlin must all pass the same strings):

- `tʃ ə` → Varg `چٚ` (not `تʃ…`)
- `m ə ʃ ə n ɒ` keeps schwa as `ٚ` on Varg / `ə` on academic-latin
- unknown phone passes through
- `lossy-persian` may collapse `ə`

Tiny generated WAV (and later a short webm) lives under `api/tests/fixtures/`; Playwright reuses it. Do not commit real user recordings.

### 12.1 Phase 1 — pytest (`api/tests/`)

- `GET /health` → 200 + `ok`
- every `schemas/presets/*.json` matches `map.schema.json`
- `GET /v1/phonology` returns the inventory
- unknown preset → 404
- `POST /v1/map` longest-match + schwa cases above
- `POST /v1/recognize` with mock + any short bytes → fixed IPA + optional `mapped_text`
- empty body → 422 `empty_audio`
- oversized → 413 `payload_too_large`
- burst over 30 / 10 min → 429
- after POST, no new files under an `uploads/` dir

### 12.2 Phase 2 — pytest + ffmpeg

- fixture WAV → 16 kHz mono in the response `audio` metadata
- duration > `MAX_DURATION_SEC` → 422 `audio_too_long`
- garbage bytes → 422 `invalid_audio`
- temp wav deleted in `finally` (no leftover files)
- missing ffmpeg (mocked) → 501 `backend_unavailable`

### 12.3 Phase 3 — deploy smoke (manual / script)

```bash
curl -sS https://1404kingstreet.com/gilaki-api/health
curl -sS -o /dev/null -w "%{http_code}" https://1404kingstreet.com/gilaki-app/
```

Expect health JSON `ok` and app HTTP 200. Confirm **18741 is closed** on the WAN.

### 12.4 Phase 4 — JS unit tests + Playwright

- Node unit tests import the web rewriter and run the shared cases in §12
- Playwright, static `web/` + mock API (`ASR_BACKEND=mock`):
  - no API key field
  - default or pasted base URL can hit mock `/health`
  - file upload of the fixture → mapped text is the visible headline
  - IPA is hidden until the optional show is on
  - changing preset remaps without a second upload
  - `lossy-persian` shows a lossy warning
  - RTL when the map `direction` is `rtl`
- Checklist (not automated): microphone capture on a real browser

Playwright talks to mock only. It is not a real-speech quality test.

### 12.5 Phase 5 — Kotlin unit tests + checklist

- Same shared rewriter cases
- Gradle asserts `applicationId` is `com.kingstreet.gilaki`
- Checklist: file pick, record, mapped headline, optional IPA, map switch without re-upload, Settings base URL override, HTTPS-only release build

### 12.6 Phase 6 — pytest + Allosaurus

- `ASR_BACKEND=mock` suite still green
- Allosaurus tests skip cleanly if the model is not installed
- When installed: phones pass alias normalize (`š` → `ʃ`, etc.); unknown symbols do not crash the rewriter
- Default Allosaurus `lang_id` is the model's own `ipa` set, returned unchanged. Orthographic maps fold inventory aliases; the IPA preset does not. `ALLOSAURUS_LANG=glk` is the optional Gilaki-only mask inside the recognizer.
- Calibration clip `api/tests/fixtures/calibration/hello-this-is-a-test.wav` is synthetic English (“Hello. This is a test.”), not a user recording and not Gilaki. `scripts/calibrate-asr.py` checks the live API against the stored unconstrained Allosaurus baseline.

### 12.7 Phase 7 — quality

- Export produces `wav` + `ipa.txt` side by side (`api/tests/test_export.py`, JS `export.test.js`, Kotlin `ExportTest`)
- Correcting IPA on the client remaps without a second upload
- `scripts/score-per.py <folder>` scores PER when `*.wav` + `*.ipa.txt` + `*.hyp.txt` triples exist; empty folder is a no-op
- Score **PER** on 20–50 local Gilaki clips. Judge maps by “a speaker can read it back.”

---

## 13. Risks and traps

- **Schwa eaten by a Persian-like map** — allowed only in `lossy-persian`, which must be labelled lossy
- **Opening 18741 to the world** — forbidden
- **Hard-coding the domain with no Settings field** — forbidden; domain may lapse
- **Changing Android applicationId after first install** — new app; do not
- **Mixing orthographies in one ASR training set** — later-phase trap
- **Fake word boundaries from a Persian tokenizer** — do not
- **GPL Allosaurus inside the APK** — do not; keep it server-side
- **Public unauthenticated ASR used as a free generic speech API** — mitigate with duration/rate limits; revisit auth if logs show abuse
- **Dialect variation** — western inventory first; do not block v1 on full dialect packs
- **Treating Grok scaffold as the product** — replace or complete it against this file; do not follow old 8080 / API-key docs

---

## 14. Repo layout

```
gilaki-ipa/
  README.md
  .gitignore
  docs/
    README.md              ← catalog + create/update rules
    PROJECT_PLAN.md        ← pointer only
    product/
      plan.md              ← this file
      design.md            ← Caspian Paper
    engineering/
      api.md
      deploy.md
      android.md
    agents/
      cursor.md
  schemas/map.schema.json
  schemas/gilaki_inventory.json
  schemas/presets/*.json
  api/                        FastAPI (`api/.env` gitignored)
  api/requirements-allosaurus.txt  optional GPL runtime, not in the APK
  .venv/                      project Python env (gitignored; created by start script)
  scripts/start-server.sh     clone-and-run on Linux
  .github/workflows/ci.yml
  web/                        web client + Playwright
  android/                    Compose client `com.kingstreet.gilaki`
  deploy/nginx-gilaki.conf
  deploy/caddy-gilaki.Caddyfile
  deploy/gilaki-api.service
  .cursor/rules/gilaki-ipa.mdc
  .cursor/rules/docs.mdc
```

Never put the master plan at repo root.

---

## 15. Git

- Local: `git init`, default branch `main`
- Remote: public `https://github.com/saeid-h/gilaki-ipa`, created with `gh` under account `saeid-h` (no need to pre-create on the website)
- Commit only when asked; stage named paths
- Never commit `.venv/`, `.env`, keystores, secrets, or model-weight caches
- `.venv/` lives at **repo root** (not under `api/`) and is already gitignored
- Push and PRs only when asked
- `.gitignore` covers `.venv/`, `.env`, `__pycache__/`, Android build dirs, `web/dist/`

---

## 16. How to use this file in Cursor

1. Open the `gilaki-ipa` folder as the workspace.
2. Read **this file**, [`docs/README.md`](../README.md) (doc rules), and `docs/product/design.md` before UI editing.
3. Do **one phase per chat**.
4. Do not resurrect accounts, S3, port 8080 as the public bind, public 18741, API keys in the apps, or a paid ASR without an explicit new decision section.

Prompt pack lives in `docs/agents/cursor.md`.

---

## 17. One-page summary

Gilaki audio goes to a FastAPI service behind `https://1404kingstreet.com/gilaki-api`, proxied to `127.0.0.1:18741`. The static app is `https://1404kingstreet.com/gilaki-app`. The service returns IPA. Web and Android (`com.kingstreet.gilaki`) apply a preset or custom map locally and show the mapped transcript; IPA is optional. Nothing paid. No API key. No user audio library on the server. If the domain is not renewed, change the base URL in Settings and in the next release.

---

## 18. Documentation rules

Catalog and create-vs-update policy: [`docs/README.md`](../README.md).

Cursor always-on rule (create in Agent if missing): `.cursor/rules/docs.mdc` — same policy as that catalog. Product rule remains `.cursor/rules/gilaki-ipa.mdc`.

Same-change: behaviour change includes the matching doc. Locked §3 needs an explicit plan revision. No second plan file. No docs at repo root except `README.md` and `LICENSE`.
