from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os
import shutil
import logging
import asyncio
from dotenv import load_dotenv

# Load environment variables before importing services
load_dotenv(dotenv_path="../.env")

from services.voice_service import voice_service
from services.llm_service import llm_service
from services.stt_service import stt_service

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "AI IELTS Speaking Assistant Backend"}

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
