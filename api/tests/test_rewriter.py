from app.rewriter import apply_map


VAR_G = {
    "id": "t",
    "name": "t",
    "script": "Arab",
    "normalize": "NFC",
    "separator": "",
    "rules": [
        {"ipa": "tʃ", "out": "چ"},
        {"ipa": "ə", "out": "ٚ"},
        {"ipa": "m", "out": "م"},
        {"ipa": "ʃ", "out": "ش"},
        {"ipa": "n", "out": "ن"},
        {"ipa": "ɒ", "out": "آ"},
    ],
}


def test_longest_match_affricate():
    assert apply_map("tʃ ə", VAR_G) == "چٚ"


def test_tie_bar_folds_during_mapping():
    assert apply_map("t͡ʃ ə", VAR_G) == "چٚ"


def test_ipa_preset_keeps_recognizer_spelling():
    from app.catalog import get_preset

    ipa = get_preset("ipa")
    assert ipa
    assert apply_map("t͡ʃ æ", ipa) == "t͡ʃ æ"


def test_schwa_and_rtl_letters():
    assert apply_map("m ə ʃ ə n ɒ", VAR_G) == "مٚشٚنآ"


def test_lossy_persian_may_collapse_schwa():
    from app.catalog import get_preset
    from app.rewriter import apply_map

    lossy = get_preset("lossy-persian")
    assert lossy and lossy.get("lossy") is True
    out = apply_map("ə", lossy)
    assert "ə" not in out
    assert out

