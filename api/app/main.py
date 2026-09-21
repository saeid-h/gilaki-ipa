from __future__ import annotations

import json
import uuid
from typing import Any

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from .asr import get_backend
from .catalog import get_preset, list_preset_summaries, load_inventory
from .ratelimit import allow
from .rewriter import apply_map
from .settings import settings

ALLOWED_DIALECTS = frozenset({"western", "eastern", "galeshi", "unspecified"})

app = FastAPI(title="Gilaki IPA API", version=settings.app_version)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list or ["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _error(status: int, code: str, message: str = "") -> HTTPException:
    body: dict = {"ok": False, "error": {"code": code}}
    if message:
        body["error"]["message"] = message
    return HTTPException(status_code=status, detail=body)


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    if request.url.path == "/health":
        return await call_next(request)
    ip = request.client.host if request.client else "unknown"
    if not allow(ip):
        return JSONResponse(
            status_code=429,
            content={"ok": False, "error": {"code": "rate_limited", "message": "Too many requests"}},
        )
    return await call_next(request)


def require_key(x_api_key: str | None = Header(default=None)) -> None:
    if settings.api_key and x_api_key != settings.api_key:
        raise _error(401, "unauthorized")


class MapRequest(BaseModel):
    ipa: str
    preset_id: str | None = None
    map: dict[str, Any] | None = None


class MapResponse(BaseModel):
    ok: bool = True
    ipa: str
    mapped_text: str
    map_used: str | None = None


@app.get("/health")
def health() -> dict:
    return {
        "ok": True,
        "status": "up",
        "backend": settings.asr_backend,
        "version": settings.app_version,
    }


@app.get("/v1/phonology")
def phonology(_: None = Depends(require_key)) -> dict:
    return {"ok": True, "inventory": load_inventory()}


@app.get("/v1/presets")
def presets(_: None = Depends(require_key)) -> dict:
    return {"ok": True, "presets": list_preset_summaries()}


@app.get("/v1/presets/{preset_id}")
def preset_detail(preset_id: str, _: None = Depends(require_key)) -> dict:
    item = get_preset(preset_id)
    if not item:
        raise _error(404, "unknown_preset")
    return {"ok": True, "preset": item}


def _resolve_map(preset_id: str | None, map_json: str | None) -> tuple[dict | None, str | None]:
    if map_json:
        try:
            payload = json.loads(map_json)
        except json.JSONDecodeError as exc:
            raise _error(422, "invalid_map", str(exc)) from exc
        return payload, payload.get("id") or "inline"
    if preset_id:
        item = get_preset(preset_id)
        if not item:
            raise _error(404, "unknown_preset")
        return item, item["id"]
    return None, None


@app.post("/v1/recognize")
async def recognize(
    audio: UploadFile = File(...),
    preset_id: str | None = Form(default=None),
    map_json: str | None = Form(default=None),
    return_mapped: bool = Form(default=True),
    dialect: str = Form(default="unspecified"),
    timestamps: bool = Form(default=False),
    _: None = Depends(require_key),
) -> dict:
    if dialect not in ALLOWED_DIALECTS:
        raise _error(422, "invalid_dialect", f"dialect must be one of {sorted(ALLOWED_DIALECTS)}")

    blob = await audio.read()
    max_bytes = settings.max_upload_mb * 1024 * 1024
    if len(blob) > max_bytes:
        raise _error(413, "payload_too_large")
    if not blob:
        raise _error(422, "empty_audio")

    backend = get_backend(settings.asr_backend)
    try:
        result = backend.recognize(blob, dialect=dialect)
    except Exception as exc:  # noqa: BLE001 — surface backend install errors cleanly
        raise _error(501, "backend_unavailable", str(exc)) from exc

    transcript_map, map_used = _resolve_map(preset_id, map_json)
    mapped = None
    if return_mapped and transcript_map:
        mapped = apply_map(result.ipa_string, transcript_map)

    phones_out: list[dict]
    if timestamps:
        phones_out = [{"ipa": p.ipa, "start": p.start, "end": p.end} for p in result.phones]
    else:
        phones_out = [{"ipa": p.ipa, "start": None, "end": None} for p in result.phones]

    # Audio bytes drop out of scope here. Do not write blob to disk.
    return {
        "ok": True,
        "request_id": uuid.uuid4().hex,
        "audio": {
            "duration_sec": result.duration_sec,
            "sample_rate": result.sample_rate,
            "filename": audio.filename,
        },
        "ipa": result.ipa_string,
        "phones": phones_out,
        "mapped_text": mapped,
        "map_used": map_used,
        "backend": result.backend,
        "dialect": dialect,
    }


@app.post("/v1/map", response_model=MapResponse)
def map_ipa(body: MapRequest, _: None = Depends(require_key)) -> MapResponse:
    if body.map:
        used = body.map.get("id") or "inline"
        text = apply_map(body.ipa, body.map)
        return MapResponse(ipa=body.ipa, mapped_text=text, map_used=used)
    if body.preset_id:
        item = get_preset(body.preset_id)
        if not item:
            raise _error(404, "unknown_preset")
        return MapResponse(ipa=body.ipa, mapped_text=apply_map(body.ipa, item), map_used=item["id"])
    raise _error(422, "map_required")
