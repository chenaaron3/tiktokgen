"""ElevenLabs with-timestamps → MP3 bytes on disk."""

from __future__ import annotations

import base64
import os
from pathlib import Path

import requests
from dotenv import load_dotenv

from narrative.providers import TextToSpeech
from util import PathUtil

# Same default voice as shortgen `voice_generator/elevenlabs.py`
DEFAULT_VOICE_ID = "NFG5qt843uXKj4pFvR7C"
DEFAULT_MODEL_ID = "eleven_v3"
DEFAULT_OUTPUT_FORMAT = "mp3_44100_128"


class ElevenLabsTts(TextToSpeech):
    """POST /v1/text-to-speech/{voice_id}/with-timestamps."""

    def __init__(
        self,
        paths: PathUtil,
        *,
        api_key: str | None = None,
        voice_id: str | None = None,
        model_id: str = DEFAULT_MODEL_ID,
        output_format: str = DEFAULT_OUTPUT_FORMAT,
        dotenv_path: Path | None = None,
    ) -> None:
        load_dotenv(dotenv_path or Path(__file__).resolve().parents[2] / ".env")
        self._paths = paths
        self._key = api_key or os.environ.get("ELEVENLABS_API_KEY")
        if not self._key:
            raise RuntimeError("ELEVENLABS_API_KEY is required")
        self._voice = voice_id or os.environ.get("ELEVENLABS_VOICE_ID") or DEFAULT_VOICE_ID
        self._model_id = model_id
        self._output_format = output_format

    def synthesize(self, script_text: str) -> Path:
        output_mp3 = self._paths.voiceover_mp3()
        if output_mp3.is_file():
            return output_mp3

        print("\n==> ElevenLabs TTS")
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{self._voice}/with-timestamps"
        headers = {"xi-api-key": self._key, "Content-Type": "application/json"}
        payload = {
            "text": script_text.strip(),
            "model_id": self._model_id,
            "output_format": self._output_format,
        }
        response = requests.post(url, headers=headers, json=payload, timeout=120)
        if not response.ok:
            raise RuntimeError(f"ElevenLabs error {response.status_code}: {response.text or response.reason}")

        data = response.json()
        audio_b64 = data.get("audio_base64")
        if not audio_b64:
            raise RuntimeError("ElevenLabs response missing audio_base64")
        output_mp3.parent.mkdir(parents=True, exist_ok=True)
        output_mp3.write_bytes(base64.b64decode(audio_b64))
        return output_mp3
