"""Local faster-whisper word timestamps (idempotent via ``whisper-words.json``)."""

from __future__ import annotations

import json

from contracts import WordToken
from narrative.providers import WordTranscriber
from util import PathUtil

WHISPER_MODEL_SIZE = "base.en"
_WHISPER_DEVICE = "cpu"
_WHISPER_COMPUTE_TYPE = "int8"


class FasterWhisperWordTranscriber(WordTranscriber):
    """Uses fixed model/device defaults; transcripts land in ``paths.whisper_words_json()``."""

    def __init__(self, paths: PathUtil) -> None:
        self._paths = paths

    def transcribe_words(self) -> list[WordToken]:
        whisper_path = self._paths.whisper_words_json()
        if whisper_path.is_file():
            raw = json.loads(whisper_path.read_text())
            return [WordToken.model_validate(w) for w in raw.get("words", [])]

        audio_mp3 = self._paths.voiceover_mp3()
        if not audio_mp3.is_file():
            raise FileNotFoundError(audio_mp3)

        try:
            from faster_whisper import WhisperModel
        except ImportError as error:
            raise RuntimeError("Install faster-whisper to transcribe audio.") from error

        print("\n==> faster-whisper")
        model = WhisperModel(
            WHISPER_MODEL_SIZE,
            device=_WHISPER_DEVICE,
            compute_type=_WHISPER_COMPUTE_TYPE,
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

        whisper_path.write_text(
            json.dumps({"words": [tok.model_dump(by_alias=True) for tok in words_out]}, indent=2) + "\n"
        )
        return words_out
