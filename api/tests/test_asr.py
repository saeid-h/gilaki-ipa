import importlib.util

import pytest

from app.asr import (
    AllosaurusBackend,
    get_backend,
    normalize_token,
    parse_allosaurus_output,
)
from app.catalog import load_inventory
from app.rewriter import apply_map
from tests.wavutil import pcm_wav

needs_allosaurus = pytest.mark.skipif(
    importlib.util.find_spec("allosaurus") is None,
    reason="allosaurus not installed",
)


def test_mock_backend_still_returns_placeholder():
    result = get_backend("mock").recognize(b"ignored")
    assert result.backend == "mock"
    assert "ə" in result.ipa_string


def test_alias_normalize_sh():
    inventory = load_inventory()
    assert normalize_token("š", inventory) == "ʃ"
    assert normalize_token("č", inventory) == "tʃ"
    assert normalize_token("æ", inventory) == "ä"


def test_unknown_symbol_does_not_crash_rewriter():
    inventory = load_inventory()
    token = normalize_token("q", inventory)
    assert token == "q"
    mapped = apply_map("q ə", {"separator": "", "rules": [{"ipa": "ə", "out": "e"}]})
    assert "q" in mapped


def test_parse_timestamp_lines():
    phones = parse_allosaurus_output("0.210 0.045 æ\n0.390 0.045 š")
    assert [p.ipa for p in phones] == ["æ", "š"]
    assert phones[0].start == pytest.approx(0.210)
    assert phones[0].end == pytest.approx(0.255)


def test_parse_plain_phones():
    phones = parse_allosaurus_output("m ə š")
    assert [p.ipa for p in phones] == ["m", "ə", "š"]


@needs_allosaurus
def test_allosaurus_does_not_crash_on_wav():
    result = AllosaurusBackend().recognize(pcm_wav(duration_sec=0.3, sample_rate=16000, channels=1))
    assert result.backend == "allosaurus"
    apply_map(result.ipa_string, {"separator": "", "rules": []})
