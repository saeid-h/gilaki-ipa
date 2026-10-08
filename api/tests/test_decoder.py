import math

from app import decoder
from app.decoder import beam_search

UNITS = ["", "a", "b", "ɑ", "x̞"]
ALIASES = {"ɑ": "ɒ", "x̞": ""}


def frames(rows):
    """rows: per frame, {unit index: log-probability}; index 0 is blank."""
    blank = [row.get(0, -20.0) for row in rows]
    idx, lp = [], []
    for row in rows:
        ranked = sorted(((s, u) for u, s in row.items() if u), reverse=True)
        ranked += [(-30.0, u) for u in range(1, len(UNITS)) if u not in row]
        idx.append([u for _, u in ranked])
        lp.append([s for s, _ in ranked])
    return blank, idx, lp


def run(rows, **kw):
    params = {"emit": 1.0, "weight": 0.0, "bonus": 0.0, "merge": True, "lm": None}
    params.update(kw)
    return beam_search(*frames(rows), UNITS, ALIASES, **params)


def test_peaky_frames_decode_like_greedy_with_raw_units_and_first_frames():
    rows = [
        {0: -5.0, 1: -0.01},
        {0: -0.01},
        {0: -3.0, 3: -0.1},
        {0: -1.0, 4: -0.5},
        {0: -4.0, 2: -0.05},
    ]
    assert run(rows) == [("a", "a", 0), ("ɒ", "ɑ", 2), ("b", "b", 4)]


def test_merge_keeps_a_phone_repeated_across_a_blank_as_one():
    rows = [{0: -5.0, 1: -0.01}, {0: -0.01}, {0: -5.0, 1: -0.01}]
    assert [p for p, _, _ in run(rows)] == ["a"]
    assert [p for p, _, _ in run(rows, merge=False)] == ["a", "a"]


def test_prior_breaks_a_close_acoustic_call():
    rows = [{0: -6.0, 1: -0.6, 2: -0.8}]
    lm = {
        "<s>": {"a": math.log(0.01), "b": math.log(0.99), "</s>": math.log(0.5)},
        "a": {"a": 0.0, "b": 0.0, "</s>": 0.0},
        "b": {"a": 0.0, "b": 0.0, "</s>": 0.0},
    }
    assert [p for p, _, _ in run(rows)] == ["a"]
    assert [p for p, _, _ in run(rows, weight=1.0, lm=lm)] == ["b"]


def test_missing_decoder_file_falls_back_to_greedy(monkeypatch, tmp_path):
    monkeypatch.setattr(decoder.settings, "decoder_path", str(tmp_path / "none.json"))
    decoder.load_decoder.cache_clear()
    try:
        assert decoder.load_decoder() is None
    finally:
        decoder.load_decoder.cache_clear()
