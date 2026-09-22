# Using this repo in Cursor

Read [`docs/product/plan.md`](../product/plan.md) before editing. One phase per chat.

Locked decisions:

- Public API: `https://1404kingstreet.com/gilaki-api`
- Public app: `https://1404kingstreet.com/gilaki-app`
- Internal bind: `127.0.0.1:18741`
- TLS via existing Caddy on 443 (this host). Do not expose 18741.
- No API key, no accounts in v1. Keep size + in-memory rate limits.
- Android applicationId: `com.kingstreet.gilaki`
- Audio and custom maps stay on device.
- Mapped text is the main result; IPA is an optional show. No in-session IPA editing.

1. Open the `gilaki-ipa` folder as the Cursor workspace.
2. Enable Agent mode. The rule in `.cursor/rules/gilaki-ipa.mdc` will load automatically.
3. Run the API locally before asking Cursor to build UI.

## Prompt pack (paste one at a time)

### 1. Finish API tests and limits

Implement pytest coverage as in `docs/product/plan.md` §12.1: `/health`, `/v1/presets`, `/v1/map`, `/v1/recognize`, schema validation, empty/oversize/rate-limit. Tiny generated WAV fixture. Keep the mock backend. Bind 127.0.0.1:18741. Do not write audio to a library.

### 2. Audio preprocessing

Add an `app/audio.py` helper that uses ffmpeg to convert any supported upload to 16 kHz mono WAV in a `NamedTemporaryFile` that is deleted in `finally`. Reject clips longer than `MAX_DURATION_SEC`. Missing ffmpeg → 501; corrupt → 422 `invalid_audio`. Tests: §12.2.

### 3. Allosaurus backend

Implement `AllosaurusBackend.recognize`: convert bytes → temp wav → `read_recognizer().recognize(...)` → tokenized phones → delete temp file. Constrain/normalize phones with `schemas/gilaki_inventory.json` aliases. Keep mock working. Tests: §12.6 (skip if model not installed).

### 4. Web app

Zero-build `web/index.html` plus a small rewriter JS module with Node unit tests (shared cases in the plan §12) and Playwright against mock. Follow `docs/product/design.md` (Caspian Paper).

- API base URL in Settings, stored in localStorage, default `https://1404kingstreet.com/gilaki-api`
- no API key field
- mic + file upload
- presets from the API
- mapped text is the headline; IPA behind an optional show
- custom map JSON editor in Settings, localStorage only
- changing map rewrites locally; never upload custom maps unless the user ticks “apply map on server”

### 5. Android

Kotlin module `com.kingstreet.gilaki` with Retrofit, Settings for base URL only (no API key), file/mic capture, Result with mapped text + optional IPA, custom map in DataStore, HTTPS-only release. Same rewriter unit tests as §12; Gradle asserts applicationId.

### 6. Quality loop

On-device IPA correction after a result, export `wav` + `ipa.txt` locally, never upload the corpus. Tests: export pair shape (Python/JS/Kotlin) and `scripts/score-per.py` no-op on an empty folder. Do not add API storage.

## Local commands

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r api/requirements.txt
cp api/.env.example api/.env
cd api && pytest
cd ../android && ./gradlew :app:testDebugUnitTest
# Linux, from repo root:
# ./scripts/start-server.sh
```
