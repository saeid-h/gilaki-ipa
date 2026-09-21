# API contract v1

Public base: `https://1404kingstreet.com/gilaki-api`  
Local base: `http://127.0.0.1:18741`

Store the base **without** a trailing slash. Paths: `base + "/health"`, `base + "/v1/recognize"`.

All successful JSON responses include `"ok": true`. Errors:

```json
{ "ok": false, "error": { "code": "payload_too_large", "message": "..." } }
```

## Auth

None in v1. If `API_KEY` is empty, auth middleware is off. Do not add an API key field to the apps.

## Endpoints

### `GET /`

JSON index so a stripped prefix `/gilaki-api/` is not a 404.

```json
{ "ok": true, "service": "gilaki-ipa", "health": "/health", "docs": "/docs" }
```

### `GET /health`

```json
{ "ok": true, "status": "up", "backend": "mock", "version": "0.1.0" }
```

### `GET /v1/phonology`

Gilaki inventory used to constrain / validate phones.

### `GET /v1/presets`

List of standard maps stored on the server.

### `GET /v1/presets/{id}`

One map document (same shape as `schemas/map.schema.json`).

### `POST /v1/recognize`

Multipart form:

| Field | Type | Required | Notes |
|---|---|---|---|
| `audio` | file | yes | wav, mp3, m4a, ogg, webm, flac |
| `preset_id` | string | no | apply this server preset |
| `map_json` | string | no | inline map JSON; overrides preset; not stored |
| `return_mapped` | bool | no | default true if preset or map sent |
| `dialect` | string | no | `western` \| `eastern` \| `galeshi` \| `unspecified` |
| `timestamps` | bool | no | default false; v1 UI ignores timestamps |

JSON response:

```json
{
  "ok": true,
  "request_id": "01J...",
  "audio": { "duration_sec": 3.21, "sample_rate": 16000 },
  "ipa": "m ə n ʃ ə n ɒ",
  "phones": [
    { "ipa": "m", "start": 0.12, "end": 0.18 },
    { "ipa": "ə", "start": 0.18, "end": 0.26 }
  ],
  "mapped_text": "مٚن شٚنا",
  "map_used": "varg-perso-arabic",
  "backend": "mock"
}
```

`phones[].start/end` may be null if the backend has no alignment.

Limits: 12 MB → 413; duration > 60 s → 422 `audio_too_long`; empty → 422 `empty_audio`; 30 req / IP / 10 min → 429.

ffmpeg missing → 501 `backend_unavailable`. Unreadable audio → 422 `invalid_audio`.

### `POST /v1/map`

Apply a map to an IPA string without audio. Useful for tests. Production clients rewrite locally.

```json
{
  "ipa": "m ə n",
  "preset_id": "varg-perso-arabic"
}
```

or `{ "ipa": "...", "map": { ...full map... } }`

## Client rules

- Prefer: recognize → IPA, then map locally.
- Send `map_json` only if you want the server to apply a custom map for that one call.
- Never send audio with a “please store this” flag in v1; there is no such flag.
- Retry only on 502/503; do not retry 413/415/422/429.
