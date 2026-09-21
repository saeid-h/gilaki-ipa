import json
from pathlib import Path

import jsonschema
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = json.loads((ROOT / "schemas" / "map.schema.json").read_text(encoding="utf-8"))
PRESETS = ROOT / "schemas" / "presets"


def test_health():
    res = client.get("/health")
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert body["status"] == "up"


def test_phonology():
    res = client.get("/v1/phonology")
    assert res.status_code == 200
    inv = res.json()["inventory"]
    assert inv["language"] == "glk"
    assert "ə" in inv["vowels"]


def test_presets():
    res = client.get("/v1/presets")
    assert res.status_code == 200
    ids = {row["id"] for row in res.json()["presets"]}
    assert "varg-perso-arabic" in ids
    assert len(ids) >= 4


def test_presets_match_schema():
    validator = jsonschema.Draft202012Validator(SCHEMA)
    files = sorted(PRESETS.glob("*.json"))
    assert files
    for path in files:
        data = json.loads(path.read_text(encoding="utf-8"))
        validator.validate(data)


def test_unknown_preset():
    res = client.get("/v1/presets/not-a-real-map")
    assert res.status_code == 404


def test_map_preset_keeps_schwa():
    res = client.post("/v1/map", json={"ipa": "m ə ʃ ə n ɒ", "preset_id": "academic-latin"})
    assert res.status_code == 200
    assert "ə" in res.json()["mapped_text"]


def test_map_longest_match_varg():
    res = client.post("/v1/map", json={"ipa": "tʃ ə", "preset_id": "varg-perso-arabic"})
    assert res.status_code == 200
    assert res.json()["mapped_text"] == "چٚ"


def test_recognize_mock():
    files = {"audio": ("clip.wav", b"RIFF....fake", "audio/wav")}
    res = client.post("/v1/recognize", files=files, data={"preset_id": "varg-perso-arabic"})
    assert res.status_code == 200
    body = res.json()
    assert body["backend"] == "mock"
    assert "ə" in body["ipa"]
    assert body["mapped_text"]


def test_recognize_empty_audio():
    files = {"audio": ("clip.wav", b"", "audio/wav")}
    res = client.post("/v1/recognize", files=files)
    assert res.status_code == 422
    assert res.json()["detail"]["error"]["code"] == "empty_audio"


def test_recognize_payload_too_large(monkeypatch):
    from app.settings import settings

    monkeypatch.setattr(settings, "max_upload_mb", 1)
    files = {"audio": ("clip.wav", b"x" * (1 * 1024 * 1024 + 1), "audio/wav")}
    res = client.post("/v1/recognize", files=files)
    assert res.status_code == 413
    assert res.json()["detail"]["error"]["code"] == "payload_too_large"


def test_rate_limit(monkeypatch):
    from app.settings import settings

    monkeypatch.setattr(settings, "rate_limit_max", 5)
    files = {"audio": ("clip.wav", b"RIFF....fake", "audio/wav")}
    last = None
    for _ in range(6):
        last = client.post("/v1/recognize", files=files)
    assert last is not None
    assert last.status_code == 429
    assert last.json()["error"]["code"] == "rate_limited"


def test_recognize_does_not_create_uploads():
    api_dir = Path(__file__).resolve().parents[1]
    uploads = api_dir / "uploads"
    existed = uploads.exists()
    files = {"audio": ("clip.wav", b"RIFF....fake", "audio/wav")}
    res = client.post("/v1/recognize", files=files)
    assert res.status_code == 200
    if not existed:
        assert not uploads.exists()
