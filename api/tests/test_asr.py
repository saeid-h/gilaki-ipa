from pathlib import Path

import importlib.util

import pytest

from app.asr import (
    AllosaurusBackend,
    allosaurus_lang_id,
    get_backend,
    inventory_unit_phones,
    normalize_token,
    parse_allosaurus_output,
)
from app.catalog import load_inventory
from app.rewriter import apply_map
from app.settings import settings
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
    assert normalize_token("ɡ", inventory) == "g"
    assert normalize_token("t͡ʃ", inventory) == "tʃ"
    assert normalize_token("y", inventory) == "ü"


def test_gilaki_unit_file_excludes_world_phones():
    phones = inventory_unit_phones()
    assert "tʃ" in phones
    assert "ə" in phones
    assert "y" in phones
    assert "ü" not in phones
    assert "æ" not in phones
    assert "θ" not in phones
    assert all(" " not in phone for phone in phones)


def test_default_allosaurus_lang_is_inventory_file():
    path = Path(allosaurus_lang_id())
    assert path.is_file()
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line]
    assert lines == inventory_unit_phones()


def test_unconstrained_allosaurus_lang(monkeypatch):
    monkeypatch.setattr(settings, "allosaurus_lang", "all")
    assert allosaurus_lang_id() == "ipa"


def test_parse_timestamp_triples_on_one_line():
    phones = parse_allosaurus_output("0.210 0.045 æ 0.390 0.045 š")
    assert [p.ipa for p in phones] == ["æ", "š"]


def test_parse_plain_phones_skips_timestamp_numbers():
    phones = parse_allosaurus_output("0.210 0.045 m ə š")
    assert [p.ipa for p in phones] == ["m", "ə", "š"]


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
