#!/usr/bin/env python3
"""Cache Allosaurus frame scores for every benchmark clip, for offline re-decoding.

Per clip: the blank log-probability of each frame and its top-K non-blank
phones with log-probabilities, after the same `ipa` mask the server uses.
Greedy decoding of this cache at emit=1 reproduces the server's phone string
exactly (checked against the existing IPA cache).

Audio comes from gitignored data/ and is never copied anywhere; the output in
data/bench/lattice/ holds scores only.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
os.environ["INVENTORY_PATH"] = str(ROOT / "schemas/gilaki_inventory.json")
os.environ["PRESETS_DIR"] = str(ROOT / "schemas/presets")
sys.path.insert(0, str(ROOT / "api"))

from app.asr import AllosaurusBackend, allosaurus_lang_id  # noqa: E402
from app.audio import prepare_audio  # noqa: E402
from app.rewriter import tokenize_ipa  # noqa: E402

DOLMA = ROOT / "data" / "dolma" / "gilaki"
CVFA = ROOT / "data" / "cv-fa"
LATTICE = ROOT / "data" / "bench" / "lattice"
TOPK = 10


def frame_scores(wav_bytes: bytes):
    from allosaurus.am.utils import move_to_tensor
    from allosaurus.audio import read_audio

    rec = AllosaurusBackend.recognizer()
    handle = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    path = Path(handle.name)
    handle.close()
    try:
        path.write_bytes(wav_bytes)
        feat = rec.pm.compute(read_audio(str(path)))
    finally:
        path.unlink(missing_ok=True)
    feats = np.expand_dims(feat, 0)
    feat_len = np.array([feat.shape[0]], dtype=np.int32)
    batch, batch_len = move_to_tensor([feats, feat_len], rec.config.device_id)
    logits = rec.am(batch, batch_len).detach().cpu().numpy()[0].copy()
    mask = rec.lm.inventory.get_mask(allosaurus_lang_id(), approximation=rec.config.approximate)
    logits = mask.mask_logits(logits)
    return logits, mask


def unit_names(mask, n_units: int) -> list[str]:
    names = [""]
    for i in range(1, n_units):
        names.append(mask.get_units([i])[0] if i in mask.unit_map else "")
    return names


def save(dest: Path, logits: np.ndarray) -> None:
    blank = logits[:, 0].astype(np.float32)
    rest = logits[:, 1:]
    idx = np.argsort(-rest, axis=1)[:, :TOPK]
    lp = np.take_along_axis(rest, idx, axis=1).astype(np.float32)
    tmp = dest.with_suffix(".tmp.npz")
    np.savez_compressed(tmp, blank=blank, idx=(idx + 1).astype(np.uint8), lp=lp)
    tmp.replace(dest)


def greedy(cache: dict, units: list[str], emit: float = 1.0, ctc: bool = False) -> list[str]:
    """Allosaurus merges a phone repeated across blanks; ctc=True keeps both, as standard CTC does."""
    out, prev = [], -1
    blank = cache["blank"] / emit
    for t in range(len(blank)):
        best = 0 if blank[t] >= cache["lp"][t, 0] else int(cache["idx"][t, 0])
        if best != prev and best != 0:
            out.append(units[best])
            prev = best
        elif ctc and best == 0:
            prev = 0
    return out


def jobs():
    import pyarrow.parquet as pq

    for split in ("train", "test"):
        table = pq.read_table(DOLMA / f"{split}-00000-of-00001.parquet", columns=["id", "audio"])
        ids = table.column("id").to_pylist()
        for i, clip_id in enumerate(ids):
            ipa = DOLMA / "cache" / split / f"{clip_id}.ipa.txt"
            if ipa.exists():
                yield f"dolma/{split}/{clip_id}", ipa, lambda i=i: table.column("audio")[i].as_py()["bytes"]
    refs = CVFA / "refs.jsonl"
    if refs.exists():
        for line in refs.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            ipa = CVFA / "cache" / f"{row['path']}.ipa.txt"
            if ipa.exists():
                yield f"persian/{row['path']}", ipa, lambda p=row["path"]: (CVFA / "clips" / p).read_bytes()


def main() -> int:
    LATTICE.mkdir(parents=True, exist_ok=True)
    units_path = LATTICE / "units.json"
    units = json.loads(units_path.read_text(encoding="utf-8")) if units_path.exists() else None
    done = mismatch = 0
    for key, ipa_path, audio in jobs():
        dest = LATTICE / f"{key}.npz"
        if dest.exists():
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        prepared = prepare_audio(audio(), max_duration_sec=60)
        logits, mask = frame_scores(prepared.wav_bytes)
        if units is None:
            units = unit_names(mask, logits.shape[1])
            units_path.write_text(json.dumps(units, ensure_ascii=False) + "\n", encoding="utf-8")
        save(dest, logits)
        if greedy(dict(np.load(dest)), units) != tokenize_ipa(ipa_path.read_text(encoding="utf-8")):
            mismatch += 1
        done += 1
        if done % 250 == 0:
            print(f"{done} cached, {mismatch} greedy mismatches", flush=True)
    print(f"done: {done} new, {mismatch} greedy mismatches")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
