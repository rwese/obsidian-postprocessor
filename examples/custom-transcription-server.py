#!/usr/bin/env python3
"""
Example Custom Transcription Server
Compatible with Obsidian Post-Processor V2 API specification

This is a minimal example implementation using FastAPI.
Replace the transcription logic with your actual transcription service.
"""

import os
import tempfile
from typing import Optional

import uvicorn
from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel


# Response models
class TranscriptionResponse(BaseModel):
    status: str = "success"
    transcription: str
    language: Optional[str] = None
    confidence: Optional[float] = None
    duration: Optional[float] = None
    model: Optional[str] = None
    metadata: Optional[dict] = None


class ErrorResponse(BaseModel):
    status: str = "error"
    error: str
    code: Optional[str] = None
    message: Optional[str] = None


# FastAPI app
app = FastAPI(
    title="Custom Transcription Service", description="Compatible with Obsidian Post-Processor V2", version="1.0.0"
)

# Security
security = HTTPBearer(auto_error=False)

# Configuration
API_KEY = os.getenv("TRANSCRIPTION_API_KEY", "your-api-key-here")
MAX_FILE_SIZE = 25 * 1024 * 1024  # 25MB
SUPPORTED_FORMATS = {".mp3", ".m4a", ".wav", ".webm", ".ogg", ".flac"}


async def verify_api_key(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify API key if provided"""
    if credentials and credentials.credentials != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return credentials


def mock_transcription(audio_data: bytes, model: str = "whisper-base", language: str = "auto") -> dict:
    """
    Mock transcription function.
    Replace this with your actual transcription service.
    """
    # This is a placeholder - replace with your actual transcription logic
    duration = len(audio_data) / 16000  # Rough estimate

    # Mock transcription based on file size (for demo purposes)
    if len(audio_data) < 1000:
        transcription = "This is a very short audio file."
    elif len(audio_data) < 10000:
        transcription = "This is a short voice memo with some content."
    else:
        transcription = "This is a longer voice memo containing multiple sentences. The transcription service has processed the audio and returned this text."

    return {
        "transcription": transcription,
        "language": "en" if language == "auto" else language,
        "confidence": 0.95,
        "duration": duration,
        "model": model,
        "metadata": {"segments": [{"start": 0.0, "end": duration, "text": transcription}]},
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "Custom Transcription Service"}


@app.post("/transcribe", response_model=TranscriptionResponse)
async def transcribe_audio(
    audio: UploadFile = File(...),
    model: Optional[str] = Form(default="whisper-base"),
    language: Optional[str] = Form(default="auto"),
    prompt: Optional[str] = Form(default=None),
    temperature: Optional[float] = Form(default=0.0),
    credentials: HTTPAuthorizationCredentials = Depends(verify_api_key),
):
    """
    Transcribe audio file to text

    - **audio**: Audio file to transcribe
    - **model**: Transcription model to use (optional)
    - **language**: Language code or "auto" for detection (optional)
    - **prompt**: Context prompt for better transcription (optional)
    - **temperature**: Temperature for transcription 0.0-1.0 (optional)
    """

    # Validate file size
    if audio.size and audio.size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail={
                "status": "error",
                "error": "File too large",
                "code": "FILE_TOO_LARGE",
                "message": f"File size {audio.size} exceeds maximum {MAX_FILE_SIZE} bytes",
            },
        )

    # Validate file format
    file_ext = os.path.splitext(audio.filename or "")[1].lower()
    if file_ext not in SUPPORTED_FORMATS:
        raise HTTPException(
            status_code=415,
            detail={
                "status": "error",
                "error": "Unsupported format",
                "code": "INVALID_FORMAT",
                "message": f"Format {file_ext} not supported. Supported: {', '.join(SUPPORTED_FORMATS)}",
            },
        )

    # Validate parameters
    if temperature and not (0.0 <= temperature <= 1.0):
        raise HTTPException(
            status_code=400,
            detail={
                "status": "error",
                "error": "Invalid temperature",
                "code": "INVALID_PARAMETER",
                "message": "Temperature must be between 0.0 and 1.0",
            },
        )

    try:
        # Read audio data
        audio_data = await audio.read()

        # Process transcription
        # Replace this with your actual transcription service
        result = mock_transcription(audio_data, model, language)

        return TranscriptionResponse(**result)

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "status": "error",
                "error": "Transcription failed",
                "code": "TRANSCRIPTION_FAILED",
                "message": str(e),
            },
        )


@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Handle HTTP exceptions with proper error format"""
    if isinstance(exc.detail, dict):
        return exc.detail
    return {"status": "error", "error": exc.detail, "code": "HTTP_ERROR"}


if __name__ == "__main__":
    print("Starting Custom Transcription Service...")
    print(f"API Key: {API_KEY}")
    print(f"Max file size: {MAX_FILE_SIZE / (1024*1024):.0f}MB")
    print(f"Supported formats: {', '.join(SUPPORTED_FORMATS)}")
    print("\nEndpoints:")
    print("  GET  /health     - Health check")
    print("  POST /transcribe - Transcribe audio")
    print("\nExample usage:")
    print("  curl -X POST http://localhost:8080/transcribe \\")
    print("    -H 'Authorization: Bearer your-api-key' \\")
    print("    -F 'audio=@recording.m4a' \\")
    print("    -F 'language=en'")
    print()

    uvicorn.run(app, host="0.0.0.0", port=8080, log_level="info")
