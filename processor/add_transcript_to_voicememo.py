#!/usr/bin/env python3
"""
Voice memo transcription processor for Obsidian using Whisper HTTP API.
Processes voice memos by transcribing them and adding transcripts to notes.
"""

import logging
import os
import re
import sys
from pathlib import Path
from typing import Optional

import requests

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class VoiceMemoTranscriber:
    """Handles voice memo transcription and note updating using Whisper HTTP API."""

    def __init__(self, api_url: str = "http://host.docker.internal:8020"):
        """Initialize the transcriber."""
        self.api_url = api_url.rstrip("/")
        self._check_api_available()

    def _check_api_available(self) -> None:
        """Check if Whisper API is available."""
        try:
            response = requests.get(f"{self.api_url}/health", timeout=10)
            response.raise_for_status()
            logger.debug("Whisper API is available")
        except requests.RequestException as e:
            raise RuntimeError(f"Whisper API is not available at {self.api_url}: {e}")

    def _get_available_models(self) -> list:
        """Get list of available models from the API."""
        try:
            response = requests.get(f"{self.api_url}/models", timeout=10)
            response.raise_for_status()
            data = response.json()
            return data.get("models", [])
        except requests.RequestException as e:
            logger.warning(f"Could not get available models: {e}")
            return []

    def _detect_language_from_filename(self, filename: str) -> Optional[str]:
        """Detect language from filename patterns like 'file_en.m4a' or 'file_de.wav'."""
        # Common language patterns in filenames
        language_patterns = {
            "_en.": "en",
            "_english.": "en",
            "_eng.": "en",
            "_de.": "de",
            "_german.": "de",
            "_deutsch.": "de",
            "_fr.": "fr",
            "_french.": "fr",
            "_francais.": "fr",
            "_es.": "es",
            "_spanish.": "es",
            "_espanol.": "es",
            "_it.": "it",
            "_italian.": "it",
            "_italiano.": "it",
            "_pt.": "pt",
            "_portuguese.": "pt",
            "_portugues.": "pt",
            "_ru.": "ru",
            "_russian.": "ru",
            "_zh.": "zh",
            "_chinese.": "zh",
            "_ja.": "ja",
            "_japanese.": "ja",
            "_ko.": "ko",
            "_korean.": "ko",
        }

        filename_lower = filename.lower()
        for pattern, lang in language_patterns.items():
            if pattern in filename_lower:
                logger.debug(f"Detected language '{lang}' from filename pattern '{pattern}'")
                return lang

        return None

    def transcribe_audio(self, audio_file_path: Path, language: Optional[str] = None, model: str = "small") -> str:
        """Transcribe audio file using Whisper HTTP API."""
        try:
            # Auto-detect language from filename if not specified
            if not language:
                language = self._detect_language_from_filename(audio_file_path.name)

            logger.info(f"Transcribing {audio_file_path.name} with model: {model}")
            if language:
                logger.info(f"Using language: {language}")
            else:
                logger.info("Using auto-detected language")

            # Prepare the request
            with open(audio_file_path, "rb") as audio_file:
                files = {"file": (audio_file_path.name, audio_file, "audio/*")}
                data = {"model": model, "output_format": "txt"}

                # Add language if specified
                if language:
                    data["language"] = language

                # Make the API request
                response = requests.post(
                    f"{self.api_url}/transcribe", files=files, data=data, timeout=600  # 10 minutes timeout
                )
                response.raise_for_status()

            # Get transcript from response
            if response.headers.get("content-type", "").startswith("application/json"):
                result = response.json()
                transcript = result.get("text", "").strip()
            else:
                # Plain text response
                transcript = response.text.strip()

            logger.info(f"Transcribed audio: {len(transcript)} characters")
            return transcript

        except requests.RequestException as e:
            logger.error(f"API request failed: {e}")
            raise RuntimeError(f"Transcription failed: {e}")
        except Exception as e:
            logger.error(f"Failed to transcribe audio: {e}")
            raise

    def read_note_content(self, note_path: Path) -> str:
        """Read the content of the note file."""
        try:
            with open(note_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            logger.error(f"Failed to read note {note_path}: {e}")
            raise

    def write_note_content(self, note_path: Path, content: str) -> None:
        """Write content to the note file."""
        try:
            with open(note_path, "w", encoding="utf-8") as f:
                f.write(content)
            logger.info(f"Updated note: {note_path}")
        except Exception as e:
            logger.error(f"Failed to write note {note_path}: {e}")
            raise

    def add_transcript_to_note(self, note_path: Path, voice_filename: str, transcript: str) -> None:
        """Add transcript to the note file."""
        try:
            # Read current content
            content = self.read_note_content(note_path)

            # Find the voice memo embed pattern
            voice_embed_pattern = rf"!\[\[{re.escape(voice_filename)}\]\]"

            # Check if transcript already exists
            transcript_pattern = rf"!\[\[{re.escape(voice_filename)}\]\]\s*\n\s*>\s*\*\*Transcript:\*\*"
            if re.search(transcript_pattern, content, re.MULTILINE | re.IGNORECASE):
                logger.info(f"Transcript already exists for {voice_filename}")
                return

            # Find the voice memo embed and add transcript after it
            def replace_embed(match):
                embed = match.group(0)
                return f"{embed}\n\n> **Transcript:**\n> {transcript}\n"

            # Replace the embed with embed + transcript
            new_content = re.sub(voice_embed_pattern, replace_embed, content)

            # Check if replacement was made
            if new_content == content:
                logger.warning(f"Voice memo embed not found for {voice_filename}")
                # Add transcript at the end of the note
                new_content += f"\n\n## Transcript for {voice_filename}\n\n> {transcript}\n"

            # Write updated content
            self.write_note_content(note_path, new_content)

        except Exception as e:
            logger.error(f"Failed to add transcript to note: {e}")
            raise

    def process_voice_memo(
        self, note_path: Path, voice_file_path: Path, language: Optional[str] = None, model: str = "small"
    ) -> bool:
        """Process a voice memo by transcribing it and adding to the note."""
        try:
            logger.info(f"Processing voice memo: {voice_file_path}")

            # Transcribe the audio
            transcript = self.transcribe_audio(voice_file_path, language, model)

            if not transcript:
                logger.warning(f"No transcript generated for {voice_file_path}")
                return False

            # Add transcript to note
            self.add_transcript_to_note(note_path, voice_file_path.name, transcript)

            logger.info(f"Successfully processed voice memo: {voice_file_path.name}")
            return True

        except Exception as e:
            logger.error(f"Failed to process voice memo: {e}")
            return False


def main():
    """Main function for the voice memo transcriber."""

    if len(sys.argv) < 3:
        logger.error("Usage: python add_transcript_to_voicememo.py <note_path> <voice_file_path>")
        sys.exit(1)

    note_path = Path(sys.argv[1])
    voice_file_path = Path(sys.argv[2])

    # Get environment variables
    vault_path = os.getenv("VAULT_PATH", "")
    log_level = os.getenv("LOG_LEVEL", "INFO")
    whisper_model = os.getenv("WHISPER_MODEL", "small")
    whisper_language = os.getenv("WHISPER_LANGUAGE", "")
    whisper_api_url = os.getenv("WHISPER_API_URL", "http://host.docker.internal:8020")

    logger.info("Processing voice memo:")
    logger.info(f"  Note: {note_path}")
    logger.info(f"  Voice file: {voice_file_path}")
    logger.info(f"  Vault path: {vault_path}")
    logger.info(f"  Log level: {log_level}")
    logger.info(f"  Whisper model: {whisper_model}")
    logger.info(f"  Whisper language: {whisper_language or 'auto-detect'}")
    logger.info(f"  Whisper API URL: {whisper_api_url}")

    # Debug: Show what files exist in the directory
    if note_path.parent.exists():
        logger.info(f"Files in note directory {note_path.parent}:")
        try:
            for file in note_path.parent.iterdir():
                if file.is_file():
                    logger.info(f"  - {file.name}")
        except Exception as e:
            logger.warning(f"Could not list directory contents: {e}")
    else:
        logger.error(f"Note directory does not exist: {note_path.parent}")

    # Check if note file exists (try with and without .md extension)
    original_note_path = note_path
    if not note_path.exists():
        # Try adding .md extension if not present
        if not note_path.name.endswith(".md"):
            note_path_with_md = note_path.with_suffix(".md")
            if note_path_with_md.exists():
                note_path = note_path_with_md
                logger.info(f"Found note file with .md extension: {note_path}")
            else:
                # Search for the note file in the vault directory
                note_found = False
                if vault_path and Path(vault_path).exists():
                    vault_root = Path(vault_path)
                    note_name = note_path.name

                    # Search for files matching the note name
                    for candidate in vault_root.rglob(f"{note_name}.md"):
                        if candidate.is_file():
                            note_path = candidate
                            note_found = True
                            logger.info(f"Found note file in vault: {note_path}")
                            break

                    # If not found with .md, try without extension
                    if not note_found:
                        for candidate in vault_root.rglob(note_name):
                            if candidate.is_file() and candidate.suffix == ".md":
                                note_path = candidate
                                note_found = True
                                logger.info(f"Found note file in vault (no ext): {note_path}")
                                break

                if not note_found:
                    logger.error(f"Note file not found: {original_note_path} or {note_path_with_md}")
                    # Additional debugging
                    logger.error(f"Note parent directory exists: {note_path.parent.exists()}")
                    logger.error(f"Note parent directory: {note_path.parent}")
                    if vault_path:
                        logger.error(f"Searched in vault: {vault_path}")
                    sys.exit(1)
        else:
            # File has .md extension but doesn't exist, try searching in vault
            note_found = False
            if vault_path and Path(vault_path).exists():
                vault_root = Path(vault_path)
                note_name = note_path.name

                # Search for files matching the note name
                for candidate in vault_root.rglob(note_name):
                    if candidate.is_file():
                        note_path = candidate
                        note_found = True
                        logger.info(f"Found note file in vault: {note_path}")
                        break

            if not note_found:
                logger.error(f"Note file not found: {note_path}")
                logger.error(f"Note parent directory exists: {note_path.parent.exists()}")
                logger.error(f"Note parent directory: {note_path.parent}")
                if vault_path:
                    logger.error(f"Searched in vault: {vault_path}")
                sys.exit(1)

    if not voice_file_path.exists():
        logger.error(f"Voice file not found: {voice_file_path}")
        sys.exit(1)

    try:
        # Initialize transcriber
        transcriber = VoiceMemoTranscriber(whisper_api_url)

        # Process the voice memo
        success = transcriber.process_voice_memo(
            note_path, voice_file_path, language=whisper_language if whisper_language else None, model=whisper_model
        )

        if success:
            logger.info("Voice memo processing completed successfully!")
            sys.exit(0)
        else:
            logger.error("Voice memo processing failed!")
            sys.exit(1)

    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
