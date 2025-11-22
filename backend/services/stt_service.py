import os
import dashscope
import logging
from http import HTTPStatus

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_KEY = os.getenv("DASHSCOPE_API_KEY")
dashscope.api_key = API_KEY

class STTService:
    def __init__(self):
        pass

    def transcribe(self, audio_file_path: str) -> str:
        """
        Transcribe audio file using Bailian (Dashscope) ASR.
        """
        try:
            # Using Paraformer model for better accuracy
            recognition = dashscope.audio.asr.Recognition(
                model='paraformer-realtime-v1', # Or just 'paraformer-v1' for file
                format='wav', # Assuming wav for now, or 'pcm'
                sample_rate=16000,
                callback=None
            )
            
            # For file transcription, we can use the simple call
            result = dashscope.audio.asr.Transcription.call(
                model='paraformer-v1',
                file_urls=[audio_file_path] # Wait, it usually takes a URL or local file path?
                # Dashscope Python SDK supports local file path for some APIs, but often requires upload.
                # Let's check if we can send bytes.
            )
            
            # Actually, for real-time or short interaction, 'Recognition' is better.
            # But 'Recognition' is for stream.
            # 'Transcription' is for file.
            
            # Let's try the simple Recognition.call for short audio
            response = dashscope.audio.asr.Recognition.call(
                model='paraformer-realtime-v1',
                format='wav',
                sample_rate=16000,
                callback=None,
                audio=audio_file_path # Local file path
            )

            if response.status_code == HTTPStatus.OK:
                # Extract text
                # Response format: {"status_code": 200, "request_id": "...", "code": "", "message": "", "output": {"sentence": [{"text": "..."}]}}
                if response.output and response.output.get("sentence"):
                    text = ""
                    for sent in response.output["sentence"]:
                        text += sent["text"]
                    return text
                return ""
            else:
                logger.error(f"ASR Error: {response.code} - {response.message}")
                return ""

        except Exception as e:
            logger.error(f"STT Exception: {e}")
            return ""

stt_service = STTService()
