from __future__ import annotations

import unicodedata
from typing import Any


def _normalize(text: str, form: str) -> str:
    return unicodedata.normalize(form, text)


def tokenize_ipa(ipa: str) -> list[str]:
    """Split an IPA string on whitespace. Multi-character phones must already be tokens."""
    return [tok for tok in ipa.replace(".", " ").replace("-", " ").split() if tok]


def apply_map(ipa: str, transcript_map: dict[str, Any]) -> str:
    form = transcript_map.get("normalize") or "NFC"
    separator = transcript_map.get("separator", "")
    unknown = transcript_map.get("unknown")
    rules = transcript_map.get("rules") or []

    # Longest IPA key first so tʃ wins over t + ʃ if someone passed a raw string.
    compiled = sorted(
        ((rule["ipa"], rule.get("out", "")) for rule in rules),
        key=lambda pair: len(pair[0]),
        reverse=True,
    )
    lookup = {src: dst for src, dst in compiled}

    tokens = tokenize_ipa(_normalize(ipa, form))
    if not tokens:
        # Fallback: greedy scan of a compact string
        compact = "".join(ipa.split())
        return _greedy(compact, compiled, unknown)

    out: list[str] = []
    for token in tokens:
        if token in lookup:
            out.append(lookup[token])
        elif unknown is not None:
            out.append(unknown)
        else:
            out.append(token)
    return _normalize(separator.join(out), form)


def _greedy(text: str, compiled: list[tuple[str, str]], unknown: str | None) -> str:
    i = 0
    chunks: list[str] = []
    while i < len(text):
        matched = False
        for src, dst in compiled:
            if text.startswith(src, i):
                chunks.append(dst)
                i += len(src)
                matched = True
                break
        if not matched:
            chunks.append(unknown if unknown is not None else text[i])
            i += 1
    return "".join(chunks)
