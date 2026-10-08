"""Re-decode Allosaurus frame scores with a Gilaki phone-pair prior.

The settings come from `schemas/phone_decoder.json`, written by
`scripts/phone-decode.py`. The beam runs over inventory phones (recognizer
units folded through the inventory aliases). Each chosen phone is returned as
the best-scoring raw unit at its frame, so the IPA line stays in the
recognizer's own symbols and clients fold it exactly as before.
"""
from __future__ import annotations

import json
import math
from collections import defaultdict
from functools import lru_cache
from pathlib import Path
from typing import Any

from .settings import settings

BOS, EOS = "<s>", "</s>"
NEG = -1e30
TOPK = 10


@lru_cache(maxsize=1)
def load_decoder() -> dict[str, Any] | None:
    path = (settings.decoder_path or "").strip()
    if not path or not Path(path).resolve().exists():
        return None
    doc = json.loads(Path(path).resolve().read_text(encoding="utf-8"))
    return doc if (doc.get("decoder") or {}).get("kind") == "beam" else None


def lae(a: float, b: float) -> float:
    if a < b:
        a, b = b, a
    if b <= NEG:
        return a
    return a + math.log1p(math.exp(b - a))


def top_frames(logits, topk: int = TOPK):
    """Blank log-probability per frame plus the top-k non-blank units (index, log-probability)."""
    import numpy as np

    rest = logits[:, 1:]
    idx = np.argsort(-rest, axis=1)[:, :topk]
    lp = np.take_along_axis(rest, idx, axis=1).astype(np.float32)
    return logits[:, 0].astype(np.float32), (idx + 1).astype(np.int64), lp


def beam_search(
    blank,
    idx,
    lp,
    units: list[str],
    aliases: dict[str, str],
    *,
    emit: float,
    weight: float,
    bonus: float,
    merge: bool,
    lm: dict[str, dict[str, float]] | None,
    beam: int = 8,
    cand_floor: float = -9.0,
    cand_max: int = 6,
) -> list[tuple[str, str, int]]:
    """CTC prefix beam search. Returns (inventory phone, raw unit, first frame) per emitted phone.

    `merge` follows Allosaurus: a phone repeated across blanks stays one phone.
    """

    def prior(ctx: str, phone: str) -> float:
        return weight * lm[ctx][phone] if weight and lm else 0.0

    beams: dict[tuple, tuple[float, float]] = {(): (0.0, NEG)}
    trace: dict[tuple, tuple] = {(): ()}
    for t in range(len(blank)):
        b = float(blank[t]) / emit
        phones: dict[str, float] = {}
        best_unit: dict[str, tuple[float, str]] = {}
        for u, s in zip(idx[t], lp[t]):
            raw = units[int(u)]
            phone = aliases.get(raw, raw) if raw else ""
            s = float(s)
            if not phone:
                b = lae(b, s)
                continue
            phones[phone] = lae(phones.get(phone, NEG), s)
            if phone not in best_unit or s > best_unit[phone][0]:
                best_unit[phone] = (s, raw)
        floor = float(lp[t][-1]) - 1.0
        cands = sorted(((s, p) for p, s in phones.items() if s > cand_floor), reverse=True)[:cand_max]
        new: dict[tuple, list[float]] = defaultdict(lambda: [NEG, NEG])
        new_trace: dict[tuple, tuple] = dict(trace)
        for prefix, (pb, pnb) in beams.items():
            tot = lae(pb, pnb)
            last = prefix[-1] if prefix else None
            cell = new[prefix]
            cell[0] = lae(cell[0], tot + b)
            if last is not None:
                cell[1] = lae(cell[1], (tot if merge else pnb) + phones.get(last, floor))
            ctx = last if last is not None else BOS
            for s, p in cands:
                if p == last:
                    if merge:
                        continue
                    src = pb
                else:
                    src = tot
                ext = prefix + (p,)
                new[ext][1] = lae(new[ext][1], src + s + prior(ctx, p) + bonus)
                new_trace.setdefault(ext, trace[prefix] + ((best_unit[p][1], t),))
        ranked = sorted(new.items(), key=lambda kv: lae(*kv[1]), reverse=True)[:beam]
        beams = {k: (v[0], v[1]) for k, v in ranked}
        trace = {k: new_trace[k] for k in beams}
    best = max(beams, key=lambda k: lae(*beams[k]) + prior(k[-1] if k else BOS, EOS))
    return [(phone, raw, frame) for phone, (raw, frame) in zip(best, trace[best])]


def decode(blank, idx, lp, units: list[str], aliases: dict[str, str], config: dict[str, Any]) -> list[tuple[str, str, int]]:
    cfg = config["decoder"]
    return beam_search(
        blank,
        idx,
        lp,
        units,
        aliases,
        emit=cfg["emit"],
        weight=cfg["weight"],
        bonus=cfg["bonus"],
        merge=cfg["merge"],
        lm=(config.get("bigram") or {}).get("logprob"),
        beam=config.get("beam", 8),
        cand_floor=config.get("cand_floor", -9.0),
        cand_max=config.get("cand_max", 6),
    )
