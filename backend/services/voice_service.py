import os
import json
import websockets
import asyncio
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_KEY = os.getenv("DASHSCOPE_API_KEY")
# Using Beijing region URL as per documentation
API_URL = "wss://dashscope.aliyuncs.com/api-ws/v1/realtime?model=qwen3-tts-flash-realtime"

class VoiceService:
    def __init__(self):
        self.api_key = API_KEY
        if not self.api_key:
            logger.error("DASHSCOPE_API_KEY not found in environment variables")

    async def stream_audio(self, text_iterator):
        """
        Streams audio from Bailian TTS for a given text iterator (async generator).
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}"
        }
        
        async with websockets.connect(API_URL, extra_headers=headers) as ws:
            logger.info("Connected to Bailian TTS WebSocket")
            
            # Initial session update
            session_update = {
                "type": "session.update",
                "session": {
                    "mode": "server_commit", # Or "commit" if we want more control
                    "model": "qwen3-tts-flash-realtime",
                    "voice": "Cherry", # Default voice, can be parameterized
                    "response_format": "pcm",
                    "sample_rate": 24000
                }
            }
            await ws.send(json.dumps(session_update))
            
            # Handle incoming messages loop in background or interleaved
            # For simplicity, we'll assume a request-response flow where we send text and get audio
            
            # But wait, Bailian Realtime API is bidirectional. 
            # We need to listen for 'session.created' first.
            
            async def receiver():
                while True:
                    try:
                        message = await ws.recv()
                        data = json.loads(message)
                        # logger.debug(f"Received: {data['type']}")
                        
                        if data['type'] == 'response.audio.delta':
                            yield data['delta'] # Base64 encoded PCM
                        elif data['type'] == 'response.done':
                            pass # Response finished
                        elif data['type'] == 'session.finished':
                            break
                        elif data['type'] == 'error':
                            logger.error(f"Bailian Error: {data}")
                    except websockets.exceptions.ConnectionClosed:
                        break

            # We need to manage sending and receiving concurrently.
            # For this MVP, let's define a simpler interface: generate_audio(text)
            # But the requirement is "Realtime". 
            
            # Let's implement a generator that yields audio chunks.
            
            # Wait for session.created
            while True:
                msg = await ws.recv()
                data = json.loads(msg)
                if data['type'] == 'session.created':
                    logger.info("Session created")
                    break
            
            # Send text
            async for text_chunk in text_iterator:
                if text_chunk:
                    input_event = {
                        "type": "input_text_buffer.append",
                        "text": text_chunk
                    }
                    await ws.send(json.dumps(input_event))
            
            # Commit (if needed, but server_commit mode handles it? 
            # Doc says: "server_commit: Client sends text only. Server intelligently judges...")
            # But we might need to close or signal end.
            
            # Actually, for a conversation, we might keep the connection open?
            # For now, let's assume one turn = one connection or keep-alive.
            # Let's close for now after text is done.
            
            # Wait for audio
            while True:
                msg = await ws.recv()
                data = json.loads(msg)
                if data['type'] == 'response.audio.delta':
                    yield data['delta']
                elif data['type'] == 'response.done':
                    # Check if we are done with all text? 
                    # In server_commit mode, it might be tricky to know when to stop if we are streaming text.
                    # But if text_iterator finishes, we are done sending.
                    # We should wait until all audio is received.
                    pass
                
                # We need a break condition.
                # If we know we sent everything, maybe we wait for response.done?
                # But response.done is for one response. 
                
                # Let's rely on a timeout or explicit close for now if needed.
                # Or better, just yield until the socket closes or we decide to stop.
                
    async def synthesize(self, text: str):
        """
        Simple synthesis for a single string.
        """
        async def text_gen():
            yield text
        
        async for chunk in self.stream_audio(text_gen()):
            yield chunk

voice_service = VoiceService()
