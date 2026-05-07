"""Local faster-whisper word timestamps."""

from __future__ import annotations

from pathlib import Path

from contracts import WordToken
from narrative.providers import WordTranscriber


class FasterWhisperWordTranscriber(WordTranscriber):
    def __init__(
        self,
        *,
        model_size: str = "base.en",
        device: str = "cpu",
        compute_type: str = "int8",
    ) -> None:
        self._model_size = model_size
        self._device = device
        self._compute_type = compute_type

    def transcribe_words(self, audio_mp3: Path) -> list[WordToken]:
        try:
            from faster_whisper import WhisperModel
        except ImportError as error:
            raise RuntimeError("Install faster-whisper to transcribe audio.") from error

        if not audio_mp3.is_file():
            raise FileNotFoundError(audio_mp3)

        model = WhisperModel(
            self._model_size,
            device=self._device,
            compute_type=self._compute_type,
        )
        segments, _info = model.transcribe(
            str(audio_mp3),
            word_timestamps=True,
        )
        words_out: list[WordToken] = []
        for segment in segments:
            for w in segment.words or []:
                words_out.append(
                    WordToken(
                        word=(w.word or "").strip(),
                        startSec=float(w.start),
                        endSec=float(w.end),
                    )
                )
        return words_out
