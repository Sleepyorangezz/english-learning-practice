import json
import logging
import os
from pathlib import Path
from typing import List, Optional

import websockets

logger = logging.getLogger(__name__)


class MiniMaxVoiceService:
    """Generate speech audio through MiniMax synchronous WebSocket API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "speech-2.6-hd",
        voice_id: str = "English_expressive_narrator",
        file_format: str = "mp3",
    ):
        self.api_key = api_key or os.getenv("MINIMAX_API_KEY")
        self.model = model
        self.voice_id = voice_id
        self.file_format = file_format

        if not self.api_key:
            logger.warning("MINIMAX_API_KEY not set. Audio synthesis will fail without it.")

    async def _connect(self):
        url = "wss://api.minimax.io/ws/v1/t2a_v2"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        return await websockets.connect(url, additional_headers=headers)

    async def synthesize(self, text: str) -> bytes:
        """Generate an audio byte string for the given text."""
        if not text.strip():
            raise ValueError("Input text for synthesis cannot be empty.")

        async with await self._connect() as ws:
            logger.info("Connected to MiniMax TTS service")

            handshake = json.loads(await ws.recv())
            if handshake.get("event") != "connected_success":
                raise RuntimeError(f"Failed to open MiniMax session: {handshake}")

            start_msg = {
                "event": "task_start",
                "model": self.model,
                "voice_setting": {
                    "voice_id": self.voice_id,
                    "speed": 1,
                    "vol": 1,
                    "pitch": 0,
                    "english_normalization": False,
                },
                "audio_setting": {
                    "sample_rate": 32000,
                    "bitrate": 128000,
                    "format": self.file_format,
                    "channel": 1,
                },
            }

            await ws.send(json.dumps(start_msg))
            started = json.loads(await ws.recv())
            if started.get("event") != "task_started":
                raise RuntimeError(f"MiniMax task did not start: {started}")

            await ws.send(
                json.dumps(
                    {
                        "event": "task_continue",
                        "text": text,
                    }
                )
            )

            audio_chunks: List[bytes] = []

            while True:
                response = json.loads(await ws.recv())

                if "data" in response and "audio" in response["data"]:
                    hex_audio = response["data"]["audio"]
                    if hex_audio:
                        audio_chunks.append(bytes.fromhex(hex_audio))

                if response.get("is_final"):
                    break

            await ws.send(json.dumps({"event": "task_finish"}))
            return b"".join(audio_chunks)

    async def synthesize_to_file(self, text: str, output_path: Path) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        audio_bytes = await self.synthesize(text)
        output_path.write_bytes(audio_bytes)
        logger.info("Saved synthesized audio to %s", output_path)
        return output_path

    async def stream_audio(self, text_iterator):
        """Compatibility layer for existing websocket flow.

        The MiniMax API returns audio after we send the full text; we therefore
        aggregate the incoming text chunks and yield a single audio payload.
        """

        collected_text = ""
        async for text_chunk in text_iterator:
            collected_text += text_chunk

        if not collected_text.strip():
            return

        yield await self.synthesize(collected_text)


voice_service = MiniMaxVoiceService()
