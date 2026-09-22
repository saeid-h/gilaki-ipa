from pathlib import Path

from app.export import export_paths, phone_error_rate, score_export_dir, write_pair


def test_export_pair_shape(tmp_path: Path):
    wav, ipa = write_pair(tmp_path, "clip-1", b"RIFF....", "m ə ʃ")
    assert wav.name == "clip-1.wav"
    assert ipa.name == "clip-1.ipa.txt"
    assert wav.read_bytes().startswith(b"RIFF")
    assert ipa.read_text(encoding="utf-8") == "m ə ʃ\n"
    assert export_paths("clip-1") == ("clip-1.wav", "clip-1.ipa.txt")


def test_phone_error_rate_substitution():
    assert phone_error_rate("a b c", "a x c") == 1 / 3
    assert phone_error_rate("tʃ ə", "tʃ ə") == 0.0
    assert phone_error_rate("", "") == 0.0
    assert phone_error_rate("", "ə") == 1.0


def test_score_export_dir_skips_unpaired(tmp_path: Path):
    write_pair(tmp_path, "a", b"wav", "m ə")
    (tmp_path / "a.hyp.txt").write_text("m a\n", encoding="utf-8")
    write_pair(tmp_path, "b", b"wav", "ʃ")
    out = score_export_dir(tmp_path)
    assert out["clip_count"] == 1
    assert out["clips"][0]["stem"] == "a"
    assert out["per"] == 0.5
