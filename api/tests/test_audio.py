import shutil
import tempfile
from pathlib import Path

import pytest

from app.audio import TEMP_PREFIX, AudioPrepError, prepare_audio
from app.settings import settings
from tests.wavutil import pcm_wav

needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")


@needs_ffmpeg
def test_prepare_resamples_to_16k_mono():
    blob = pcm_wav(duration_sec=0.25, sample_rate=44100, channels=2)
    prepared = prepare_audio(blob, max_duration_sec=settings.max_duration_sec)
    assert prepared.sample_rate == 16000
    assert 0.2 <= prepared.duration_sec <= 0.3
    assert prepared.wav_bytes[:4] == b"RIFF"


@needs_ffmpeg
def test_prepare_rejects_too_long(monkeypatch):
    blob = pcm_wav(duration_sec=1.0, sample_rate=16000, channels=1)
    with pytest.raises(AudioPrepError) as exc:
        prepare_audio(blob, max_duration_sec=0.2)
    assert exc.value.status == 422
    assert exc.value.code == "audio_too_long"


@needs_ffmpeg
def test_prepare_rejects_garbage():
    with pytest.raises(AudioPrepError) as exc:
        prepare_audio(b"not-audio-at-all", max_duration_sec=60)
    assert exc.value.status == 422
    assert exc.value.code == "invalid_audio"


@needs_ffmpeg
def test_prepare_deletes_temp_files():
    tmp = Path(tempfile.gettempdir())
    before = set(tmp.glob(f"{TEMP_PREFIX}*"))
    prepare_audio(pcm_wav(), max_duration_sec=60)
    after = set(tmp.glob(f"{TEMP_PREFIX}*"))
    assert after == before


def test_prepare_missing_ffmpeg(monkeypatch):
    monkeypatch.setattr("app.audio.ffmpeg_path", lambda: None)
    with pytest.raises(AudioPrepError) as exc:
        prepare_audio(pcm_wav(), max_duration_sec=60)
    assert exc.value.status == 501
    assert exc.value.code == "backend_unavailable"
