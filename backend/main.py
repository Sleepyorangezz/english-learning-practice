import logging
import os
import re
from pathlib import Path
from typing import List
from uuid import uuid4

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Load environment variables before importing services
load_dotenv(dotenv_path="../.env")

from services.voice_service import voice_service
from services.llm_service import llm_service
from services.stt_service import stt_service

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

MEDIA_DIR = Path(__file__).parent / "generated_audio"
MEDIA_DIR.mkdir(parents=True, exist_ok=True)
FRONTEND_DIR = Path(__file__).parent.parent / "frontend"

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/media", StaticFiles(directory=str(MEDIA_DIR)), name="media")
app.mount("/web", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")


class ListeningRequest(BaseModel):
    text: str


def _split_sentences(text: str) -> List[str]:
    pieces = re.split(r"(?<=[.!?。！？])\s+", text.strip())
    return [p.strip() for p in pieces if p.strip()]


def _build_subtitles(text: str) -> List[dict]:
    sentences = _split_sentences(text)
    subtitles = []
    cursor = 0.0
    for idx, sentence in enumerate(sentences):
        words = len(sentence.split())
        duration = max(1.8, words * 0.35)
        subtitles.append(
            {
                "id": idx,
                "text": sentence,
                "start": round(cursor, 2),
                "duration": round(duration, 2),
            }
        )
        cursor += duration
    return subtitles

@app.get("/")
def read_root():
    return {"message": "AI IELTS Speaking Assistant Backend"}


@app.post("/api/listening")
async def generate_listening(request: ListeningRequest):
    text = request.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Text input is required for listening synthesis.")

    filename = f"listening-{uuid4().hex}.{voice_service.file_format}"
    file_path = MEDIA_DIR / filename

    try:
        await voice_service.synthesize_to_file(text, file_path)
    except Exception as exc:
        logger.error("MiniMax synthesis failed: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to synthesize audio with MiniMax.") from exc

    subtitles = _build_subtitles(text)

    return {
        "audio_url": f"/media/{filename}",
        "subtitles": subtitles,
    }

@app.websocket("/ws/chat")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info("WebSocket connected")
    
    try:
        while True:
            # Receive message
            # We expect the client to send either JSON (control/text) or Bytes (audio)
            # For MVP, let's assume client sends a JSON with "type" and "data"
            # Or simpler: Client sends audio bytes directly for voice input.
            
            data = await websocket.receive()
            
            if "bytes" in data:
                # Handle Audio Input
                audio_bytes = data["bytes"]
                logger.info(f"Received audio bytes: {len(audio_bytes)}")
                
                # Save to temp file for STT (Dashscope might need file)
                temp_filename = "temp_input.wav"
                with open(temp_filename, "wb") as f:
                    f.write(audio_bytes)
                
                # 1. STT
                user_text = stt_service.transcribe(temp_filename)
                logger.info(f"Transcribed text: {user_text}")
                
                if not user_text:
                    await websocket.send_json({"type": "error", "message": "Could not understand audio"})
                    continue

                # Send transcription back to UI
                await websocket.send_json({"type": "transcription", "text": user_text, "role": "user"})
                
                # 2. LLM
                # We need to maintain conversation history. 
                # For this simple MVP, we'll just send the current input + system prompt.
                # Ideally, we should store history in a session or pass it from client.
                # Let's ask client to send history? Or keep it here in memory for the connection.
                
                # Simple history in memory for this connection
                if not hasattr(websocket, "history"):
                    websocket.history = []
                
                websocket.history.append({"role": "user", "content": user_text})
                
                # Stream LLM response
                llm_response_text = ""
                await websocket.send_json({"type": "status", "status": "thinking"})
                
                # We can stream text to client AND stream text to TTS.
                # To do this efficiently, we need to be careful.
                # Let's accumulate text for TTS or stream it chunk by chunk if TTS supports it.
                # Bailian TTS supports streaming text input.
                
                # Let's create a generator for LLM output
                async def llm_generator():
                    nonlocal llm_response_text
                    for chunk in llm_service.get_response(websocket.history):
                        llm_response_text += chunk
                        # Send text chunk to UI
                        await websocket.send_json({"type": "text_delta", "delta": chunk})
                        yield chunk
                
                # 3. TTS & Audio Stream
                await websocket.send_json({"type": "status", "status": "speaking"})
                
                async for audio_chunk in voice_service.stream_audio(llm_generator()):
                    # Send audio chunk to client
                    # We can send raw bytes
                    await websocket.send_bytes(audio_chunk)
                
                # Update history with full response
                websocket.history.append({"role": "assistant", "content": llm_response_text})
                
                await websocket.send_json({"type": "response_done"})
                await websocket.send_json({"type": "status", "status": "listening"})

            elif "text" in data:
                # Handle Text Input (if any)
                pass
                
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        try:
            await websocket.close()
        except:
            pass

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
