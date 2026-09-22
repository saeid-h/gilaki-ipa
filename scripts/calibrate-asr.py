#!/usr/bin/env python3
"""Score the synthetic English calibration clip against the live recognizer.

The clip is "Hello. This is a test." spoken by macOS `say`, not a person and not Gilaki.
The public API returns the model's own phones. A mismatch against the stored
unconstrained baseline means the server decoder changed. PER against the spoken
reference stays above zero because the model still misses and substitutes phones.
"""
from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "api"))

from app.export import phone_error_rate  # noqa: E402

CLIP = ROOT / "api/tests/fixtures/calibration/hello-this-is-a-test.wav"
META = ROOT / "api/tests/fixtures/calibration/hello-this-is-a-test.json"
DEFAULT_API = "https://1404kingstreet.com/gilaki-api"


def recognize(api: str, wav: Path) -> dict:
    boundary = "----gilaki-calibrate"
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="audio"; filename="{wav.name}"\r\n'
        "Content-Type: audio/wav\r\n\r\n"
    ).encode() + wav.read_bytes() + f"\r\n--{boundary}\r\n".encode()
    body += (
        f'Content-Disposition: form-data; name="preset_id"\r\n\r\nipa\r\n'
        f"--{boundary}--\r\n"
    ).encode()
    req = urllib.request.Request(
        api.rstrip("/") + "/v1/recognize",
        data=body,
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "User-Agent": "gilaki-calibrate",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as res:
        return json.loads(res.read().decode())


def main() -> int:
    api = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_API
    meta = json.loads(META.read_text(encoding="utf-8"))
    data = recognize(api, CLIP)
    hyp = data.get("ipa") or ""
    reference = meta["reference"]
    gilaki = meta["baselines"]["allosaurus_gilaki"]
    raw = meta["baselines"]["allosaurus_ipa"]
    print(f"utterance: {meta['utterance']}")
    print(f"spoken:    {reference}")
    print(f"raw model: {raw}")
    print(f"gilaki:    {gilaki}")
    print(f"server:    {hyp}")
    print(f"PER vs spoken:  {phone_error_rate(reference, hyp):.3f}")
    print(f"PER vs model baseline: {phone_error_rate(raw, hyp):.3f}")
    print(f"backend: {data.get('backend')}")
    return 0 if hyp == raw else 1


if __name__ == "__main__":
    raise SystemExit(main())
