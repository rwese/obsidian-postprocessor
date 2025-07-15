"""Voice memo processing logic for Obsidian Post-Processor V2."""

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiohttp

from ..parser import ParsedNote
from ..scanner import NoteInfo

logger = logging.getLogger(__name__)


@dataclass
class ProcessResult:
    """Result of processing a voice memo."""

    success: bool
    processor_name: str
    note_path: Path
    message: str
    output: Optional[str] = None
    error: Optional[str] = None
    processing_time: float = 0.0
    retry_count: int = 0


class ProcessingError(Exception):
    """Exception raised during voice memo processing."""

    def __init__(self, message: str, processor_name: str, note_path: Path, recoverable: bool = True):
        super().__init__(message)
        self.processor_name = processor_name
        self.note_path = note_path
        self.recoverable = recoverable


class BaseProcessor(ABC):
    """Base class for all voice memo processors."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.timeout = config.get("timeout", 300)
        self.retry_attempts = config.get("retry_attempts", 3)

    @abstractmethod
    async def can_process(self, note_info: NoteInfo, parsed_note: ParsedNote) -> bool:
        """Check if processor can handle this note."""
        pass

    @abstractmethod
    async def process(self, note_info: NoteInfo, parsed_note: ParsedNote) -> ProcessResult:
        """Execute processing logic."""
        pass

    @abstractmethod
    async def cleanup(self, note_info: NoteInfo, parsed_note: ParsedNote):
        """Post-processing cleanup."""
        pass

    async def process_with_timeout(self, note_info: NoteInfo, parsed_note: ParsedNote) -> ProcessResult:
        """Process with timeout and error handling."""
        start_time = time.time()

        try:
            result = await asyncio.wait_for(self.process(note_info, parsed_note), timeout=self.timeout)
            result.processing_time = time.time() - start_time
            return result

        except asyncio.TimeoutError:
            processing_time = time.time() - start_time
            return ProcessResult(
                success=False,
                processor_name=self.__class__.__name__,
                note_path=note_info.note_path,
                message=f"Processing timed out after {self.timeout}s",
                error="timeout",
                processing_time=processing_time,
            )
        except Exception as e:
            processing_time = time.time() - start_time
            return ProcessResult(
                success=False,
                processor_name=self.__class__.__name__,
                note_path=note_info.note_path,
                message=f"Processing failed: {str(e)}",
                error=str(e),
                processing_time=processing_time,
            )


class WhisperProcessor(BaseProcessor):
    """OpenAI Whisper API processor for transcription."""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_key = config.get("api_key", "dummy-key")  # Some self-hosted APIs don't need real keys
        self.base_url = config.get("base_url", "https://api.openai.com/v1")
        self.model = config.get("model", "whisper-1")
        self.language = config.get("language", "auto")
        self.temperature = config.get("temperature", 0.0)
        self.prompt = config.get("prompt", "")
        self.use_custom_api = config.get("use_custom_api", False)

    async def can_process(self, note_info: NoteInfo, parsed_note: ParsedNote) -> bool:
        """Check if note has audio attachments."""
        return len(note_info.attachments) > 0

    async def process(self, note_info: NoteInfo, parsed_note: ParsedNote) -> ProcessResult:
        """Transcribe audio attachments using OpenAI Whisper."""
        if not note_info.attachments:
            return ProcessResult(
                success=False,
                processor_name="WhisperProcessor",
                note_path=note_info.note_path,
                message="No audio attachments found",
            )

        # Process first attachment for now
        audio_file = note_info.attachments[0]

        try:
            transcript = await self._transcribe_audio(audio_file)

            # Insert transcription into note content instead of frontmatter
            await self._insert_transcription_into_note(note_info.note_path, audio_file, transcript)

            return ProcessResult(
                success=True,
                processor_name="WhisperProcessor",
                note_path=note_info.note_path,
                message=f"Successfully transcribed {audio_file.name}",
                output=None,  # Don't store in frontmatter
            )

        except Exception as e:
            return ProcessResult(
                success=False,
                processor_name="WhisperProcessor",
                note_path=note_info.note_path,
                message=f"Transcription failed: {str(e)}",
                error=str(e),
            )

    async def _transcribe_audio(self, audio_file: Path) -> str:
        """Transcribe audio file using Whisper API (OpenAI or self-hosted)."""
        if self.use_custom_api:
            return await self._transcribe_custom_api(audio_file)
        else:
            return await self._transcribe_openai_api(audio_file)

    async def _transcribe_openai_api(self, audio_file: Path) -> str:
        """Transcribe using OpenAI-compatible API."""
        import openai

        # Create client with custom base URL for self-hosted APIs
        client = openai.OpenAI(api_key=self.api_key, base_url=self.base_url)

        with open(audio_file, "rb") as f:
            transcript = client.audio.transcriptions.create(
                model=self.model,
                file=f,
                language=self.language if self.language != "auto" else None,
                temperature=self.temperature,
                prompt=self.prompt if self.prompt else None,
            )

        return transcript.text

    async def _transcribe_custom_api(self, audio_file: Path) -> str:
        """Transcribe using custom async API."""

        # Remove /v1 suffix from base_url for custom API
        api_url = self.base_url.rstrip("/v1")

        async with aiohttp.ClientSession() as session:
            # Submit transcription task
            with open(audio_file, "rb") as f:
                data = aiohttp.FormData()
                data.add_field("file", f, filename=audio_file.name)
                data.add_field("model", self.model)
                data.add_field("output_format", "json")
                if self.language and self.language != "auto":
                    data.add_field("language", self.language)

                async with session.post(f"{api_url}/transcribe/async", data=data) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise Exception(f"Failed to submit transcription: {error_text}")

                    task_info = await response.json()
                    task_id = task_info["task_id"]

            # Poll for completion
            max_wait = 300  # 5 minutes timeout
            start_time = time.time()

            while time.time() - start_time < max_wait:
                async with session.get(f"{api_url}/tasks/{task_id}") as response:
                    if response.status != 200:
                        raise Exception(f"Failed to check task status: {await response.text()}")

                    status = await response.json()

                    if status["status"] == "completed":
                        # Get result
                        async with session.get(f"{api_url}/tasks/{task_id}/result") as result_response:
                            if result_response.status != 200:
                                raise Exception(f"Failed to get result: {await result_response.text()}")

                            result_data = await result_response.json()
                            return result_data["text"]

                    elif status["status"] == "failed":
                        raise Exception(f'Transcription failed: {status.get("error_message", "Unknown error")}')

                    # Wait before next poll
                    await asyncio.sleep(2)

            raise Exception(f"Transcription timed out after {max_wait} seconds")

    async def _insert_transcription_into_note(self, note_path: Path, audio_file: Path, transcript: str):
        """Insert transcription into note content as a quoted block."""
        import re

        # Read current content
        content = note_path.read_text(encoding="utf-8")

        # Find the audio attachment reference
        audio_filename = audio_file.name
        patterns = [
            rf"!\[\[{re.escape(audio_filename)}\]\]",  # Obsidian wiki link
            rf"!\[.*?\]\([^\)]*{re.escape(audio_filename)}[^\)]*\)",  # Markdown link
        ]

        # Look for existing transcription block after the audio file
        transcription_pattern = r"(> \*\*Transcript:\*\*[\s\S]*?)(?=\n\n|\n!\[|\n#|$)"

        # Create new transcription block
        transcription_block = f"\n\n> **Transcript:**\n> {transcript}\n"

        # Find the audio reference and handle transcription
        for pattern in patterns:
            matches = list(re.finditer(pattern, content, re.IGNORECASE))
            if matches:
                # Use the first match
                match = matches[0]
                match_end = match.end()

                # Check if there's already a transcription block after this audio file
                remaining_content = content[match_end:]
                existing_transcription = re.search(transcription_pattern, remaining_content)

                if existing_transcription:
                    # Replace existing transcription
                    start_pos = match_end + existing_transcription.start()
                    end_pos = match_end + existing_transcription.end()
                    content = content[:start_pos] + transcription_block + content[end_pos:]
                else:
                    # Insert new transcription block after the audio file
                    content = content[:match_end] + transcription_block + content[match_end:]

                break

        # Write updated content
        note_path.write_text(content, encoding="utf-8")

    async def cleanup(self, note_info: NoteInfo, parsed_note: ParsedNote):
        """No cleanup needed for Whisper processor."""
        pass


class ScriptProcessor(BaseProcessor):
    """External script processor for custom processing."""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.command = config.get("command", "")
        self.env = config.get("env", {})

        if not self.command:
            raise ValueError("Command is required for Script processor")

    async def can_process(self, note_info: NoteInfo, parsed_note: ParsedNote) -> bool:
        """Check if note has audio attachments."""
        return len(note_info.attachments) > 0

    async def process(self, note_info: NoteInfo, parsed_note: ParsedNote) -> ProcessResult:
        """Execute external script for processing."""
        if not note_info.attachments:
            return ProcessResult(
                success=False,
                processor_name="ScriptProcessor",
                note_path=note_info.note_path,
                message="No audio attachments found",
            )

        # Process first attachment
        audio_file = note_info.attachments[0]

        try:
            output = await self._run_script(audio_file, note_info.note_path)

            return ProcessResult(
                success=True,
                processor_name="ScriptProcessor",
                note_path=note_info.note_path,
                message=f"Successfully processed {audio_file.name}",
                output=output,
            )

        except Exception as e:
            return ProcessResult(
                success=False,
                processor_name="ScriptProcessor",
                note_path=note_info.note_path,
                message=f"Script execution failed: {str(e)}",
                error=str(e),
            )

    async def _run_script(self, audio_file: Path, note_file: Path) -> str:
        """Execute external script."""
        import os

        # Format command with file paths
        formatted_command = self.command.format(audio_file=str(audio_file), note_file=str(note_file))

        # Prepare environment
        env = os.environ.copy()
        env.update(self.env)

        # Execute command
        process = await asyncio.create_subprocess_shell(
            formatted_command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, env=env
        )

        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            error_msg = stderr.decode("utf-8") if stderr else "Script execution failed"
            raise ProcessingError(
                message=error_msg, processor_name="ScriptProcessor", note_path=note_file, recoverable=True
            )

        return stdout.decode("utf-8")

    async def cleanup(self, note_info: NoteInfo, parsed_note: ParsedNote):
        """No cleanup needed for Script processor."""
        pass


class CustomApiProcessor(BaseProcessor):
    """Custom API processor for external transcription services following the documented API format."""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_url = config.get("api_url")
        self.api_key = config.get("api_key")
        self.model = config.get("model", "whisper-base")
        self.language = config.get("language", "auto")
        self.temperature = config.get("temperature", 0.0)
        self.prompt = config.get("prompt")
        self.state_manager = None  # Will be set by orchestration layer

        if not self.api_url:
            raise ValueError("api_url is required for CustomApi processor")

    def set_state_manager(self, state_manager):
        """Set the state manager for task persistence."""
        self.state_manager = state_manager

    async def can_process(self, note_info: NoteInfo, parsed_note: ParsedNote) -> bool:
        """Check if note has audio attachments."""
        return len(note_info.attachments) > 0

    async def process(self, note_info: NoteInfo, parsed_note: ParsedNote) -> ProcessResult:
        """Transcribe audio attachments using custom API."""
        if not note_info.attachments:
            return ProcessResult(
                success=False,
                processor_name="CustomApiProcessor",
                note_path=note_info.note_path,
                message="No audio attachments found",
            )

        # Process first attachment for now
        audio_file = note_info.attachments[0]

        try:
            # Check for existing task ID first
            existing_task_id = None
            if self.state_manager:
                existing_task_id = await self.state_manager.get_existing_task_id(
                    note_info.note_path, "CustomApiProcessor"
                )

            transcript = await self._transcribe_audio(
                audio_file, note_info.note_path, existing_task_id=existing_task_id
            )

            # Insert transcription into note content
            await self._insert_transcription_into_note(note_info.note_path, audio_file, transcript)

            return ProcessResult(
                success=True,
                processor_name="CustomApiProcessor",
                note_path=note_info.note_path,
                message=f"Successfully transcribed {audio_file.name}",
                output=transcript,
            )

        except Exception as e:
            return ProcessResult(
                success=False,
                processor_name="CustomApiProcessor",
                note_path=note_info.note_path,
                message=f"Transcription failed: {str(e)}",
                error=str(e),
            )

    async def _transcribe_audio(self, audio_file: Path, note_path: Path, existing_task_id: Optional[str] = None) -> str:
        """Transcribe audio file using custom API with task polling."""

        timeout = aiohttp.ClientTimeout(total=self.timeout)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            headers = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            # If we have an existing task_id, resume polling instead of submitting new request
            if existing_task_id:
                logger.info(f"Resuming polling for existing task {existing_task_id}")
                return await self._poll_task_completion(session, existing_task_id, headers)

            # Read the file content for new submission
            with open(audio_file, "rb") as f:
                audio_data = f.read()

            data = aiohttp.FormData()

            # Add audio file data (API expects 'file' parameter)
            data.add_field("file", audio_data, filename=audio_file.name)

            # Add optional parameters
            if self.model:
                data.add_field("model", self.model)
            if self.language and self.language != "auto":
                data.add_field("language", self.language)
            if self.prompt:
                data.add_field("prompt", self.prompt)

            # Add output_format for structured response
            data.add_field("output_format", "json")

            # Use async endpoint according to API docs
            async_endpoint = self.api_url
            if not async_endpoint.endswith("/async"):
                async_endpoint = async_endpoint.rstrip("/") + "/async"

            logger.info(f"Submitting to async endpoint: {async_endpoint}")

            # Submit transcription request to async endpoint
            async with session.post(async_endpoint, data=data, headers=headers) as response:
                if response.status == 200:
                    result = await response.json()

                    # CustomApiProcessor ONLY does async processing - MUST return task_id
                    if "task_id" in result or "id" in result:
                        task_id = result.get("task_id") or result.get("id")
                        logger.info(f"Received task ID {task_id} from API, storing in frontmatter")

                        # Store task_id in frontmatter immediately
                        if self.state_manager:
                            await self.state_manager.mark_task_submitted(note_path, "CustomApiProcessor", task_id)

                        return await self._poll_task_completion(session, task_id, headers)
                    else:
                        raise Exception(f"CustomApiProcessor requires async response with task_id. Got: {result}")
                else:
                    error_text = await response.text()
                    raise Exception(f"HTTP {response.status}: {error_text}")

    async def _poll_task_completion(self, session: aiohttp.ClientSession, task_id: str, headers: dict) -> str:
        """Poll task status until completion and return transcription."""
        from urllib.parse import urlparse

        # Parse base URL from api_url
        parsed = urlparse(self.api_url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"

        # Use correct API endpoint according to docs: GET /tasks/{task_id}
        status_endpoint = f"{base_url}/tasks/{task_id}"

        start_time = time.time()
        poll_interval = 2.0  # Start with 2 second intervals
        max_interval = 10.0  # Cap at 10 seconds

        while time.time() - start_time < self.timeout:
            try:
                async with session.get(status_endpoint, headers=headers) as response:
                    if response.status == 200:
                        status_data = await response.json()

                        # Check task status
                        status = status_data.get("status")

                        if status in ["completed", "success", "done"]:
                            # Get result using the result endpoint
                            return await self._get_task_result(session, task_id, headers, base_url)

                        elif status in ["failed", "error"]:
                            error_msg = (
                                status_data.get("error")
                                or status_data.get("error_message")
                                or status_data.get("message")
                                or "Task failed"
                            )
                            raise Exception(f"Transcription failed: {error_msg}")

                        elif status in ["pending", "running", "processing", "queued"]:
                            # Task still processing, continue polling
                            logger.debug(f"Task {task_id} status: {status}, continuing to poll...")
                        else:
                            logger.warning(f"Unknown task status: {status}")

                    elif response.status == 404:
                        raise Exception(f"Task {task_id} not found")
                    else:
                        logger.warning(f"Error checking task status: HTTP {response.status}")

            except aiohttp.ClientError as e:
                logger.warning(f"Network error checking task status: {e}")

            # Wait before next poll with exponential backoff
            await asyncio.sleep(poll_interval)
            poll_interval = min(poll_interval * 1.2, max_interval)

        raise Exception(f"Transcription timed out after {self.timeout} seconds")

    async def _get_task_result(self, session: aiohttp.ClientSession, task_id: str, headers: dict, base_url: str) -> str:
        """Retrieve task result using the correct API endpoint."""

        # Use correct API endpoint according to docs: GET /tasks/{task_id}/result
        result_endpoint = f"{base_url}/tasks/{task_id}/result"

        try:
            async with session.get(result_endpoint, headers=headers) as response:
                if response.status == 200:
                    result_data = await response.json()

                    # Extract transcription text from response
                    transcription = (
                        result_data.get("transcription") or result_data.get("text") or result_data.get("result")
                    )

                    if transcription:
                        return transcription
                    else:
                        raise Exception(f"No transcription found in result: {result_data}")
                else:
                    error_text = await response.text()
                    raise Exception(f"Failed to get result: HTTP {response.status} - {error_text}")

        except aiohttp.ClientError as e:
            raise Exception(f"Network error getting task result: {e}")

    async def _insert_transcription_into_note(self, note_path: Path, audio_file: Path, transcript: str):
        """Insert transcription into note content as a quoted block."""
        import re

        # Read current content
        content = note_path.read_text(encoding="utf-8")

        # Find the audio attachment reference
        audio_filename = audio_file.name
        patterns = [
            rf"!\[\[{re.escape(audio_filename)}\]\]",  # Obsidian wiki link
            rf"!\[.*?\]\([^\)]*{re.escape(audio_filename)}[^\)]*\)",  # Markdown link
        ]

        # Look for existing transcription block after the audio file
        transcription_pattern = r"(> \*\*Transcript:\*\*[\s\S]*?)(?=\n\n|\n!\[|\n#|$)"

        # Create new transcription block
        transcription_block = f"\n\n> **Transcript:**\n> {transcript}\n"

        # Find the audio reference and handle transcription
        for pattern in patterns:
            matches = list(re.finditer(pattern, content, re.IGNORECASE))
            if matches:
                # Use the first match
                match = matches[0]
                match_end = match.end()

                # Check if there's already a transcription block after this audio file
                remaining_content = content[match_end:]
                existing_transcription = re.search(transcription_pattern, remaining_content)

                if existing_transcription:
                    # Replace existing transcription
                    start_pos = match_end + existing_transcription.start()
                    end_pos = match_end + existing_transcription.end()
                    content = content[:start_pos] + transcription_block + content[end_pos:]
                else:
                    # Insert new transcription block after the audio file
                    content = content[:match_end] + transcription_block + content[match_end:]

                break

        # Write updated content
        note_path.write_text(content, encoding="utf-8")

    async def cleanup(self, note_info: NoteInfo, parsed_note: ParsedNote):
        """No cleanup needed for CustomApi processor."""
        pass


class ProcessorRegistry:
    """Registry for managing voice memo processors."""

    def __init__(self, state_manager=None):
        self.processors: Dict[str, BaseProcessor] = {}
        self.state_manager = state_manager
        self.processor_types = {
            "whisper": WhisperProcessor,
            "script": ScriptProcessor,
            "custom_api": CustomApiProcessor,
        }

    def register_processor(self, name: str, processor: BaseProcessor):
        """Register a processor instance."""
        self.processors[name] = processor
        logger.info(f"Registered processor: {name}")

    def create_processor(self, name: str, processor_type: str, config: Dict[str, Any]) -> BaseProcessor:
        """Create and register a processor from configuration."""
        if processor_type not in self.processor_types:
            raise ValueError(f"Unknown processor type: {processor_type}")

        processor_class = self.processor_types[processor_type]
        processor = processor_class(config)

        # Set state manager for processors that support it
        if hasattr(processor, "set_state_manager") and self.state_manager:
            processor.set_state_manager(self.state_manager)

        self.register_processor(name, processor)
        return processor

    def get_processor(self, name: str) -> Optional[BaseProcessor]:
        """Get a registered processor."""
        return self.processors.get(name)

    def list_processors(self) -> List[str]:
        """List all registered processors."""
        return list(self.processors.keys())

    async def process_note(self, processor_name: str, note_info: NoteInfo, parsed_note: ParsedNote) -> ProcessResult:
        """Process a note with a specific processor."""
        processor = self.get_processor(processor_name)
        if not processor:
            return ProcessResult(
                success=False,
                processor_name=processor_name,
                note_path=note_info.note_path,
                message=f"Processor not found: {processor_name}",
                error="processor_not_found",
            )

        # Check if processor can handle this note
        if not await processor.can_process(note_info, parsed_note):
            return ProcessResult(
                success=False,
                processor_name=processor_name,
                note_path=note_info.note_path,
                message=f"Processor {processor_name} cannot process this note",
                error="cannot_process",
            )

        # Process with retry logic
        last_error = None
        for attempt in range(processor.retry_attempts):
            try:
                result = await processor.process_with_timeout(note_info, parsed_note)
                result.retry_count = attempt

                if result.success:
                    return result

                last_error = result.error

                # Wait before retry
                if attempt < processor.retry_attempts - 1:
                    await asyncio.sleep(1.0 * (2**attempt))  # Exponential backoff

            except Exception as e:
                last_error = str(e)
                if attempt < processor.retry_attempts - 1:
                    await asyncio.sleep(1.0 * (2**attempt))

        return ProcessResult(
            success=False,
            processor_name=processor_name,
            note_path=note_info.note_path,
            message=f"Processing failed after {processor.retry_attempts} attempts",
            error=last_error,
            retry_count=processor.retry_attempts,
        )

    async def cleanup_processor(self, processor_name: str, note_info: NoteInfo, parsed_note: ParsedNote):
        """Run cleanup for a processor."""
        processor = self.get_processor(processor_name)
        if processor:
            try:
                await processor.cleanup(note_info, parsed_note)
            except Exception as e:
                logger.warning(f"Cleanup failed for processor {processor_name}: {e}")


def create_processor_registry_from_config(processors_config: Dict[str, Any], state_manager=None) -> ProcessorRegistry:
    """Create processor registry from configuration."""
    registry = ProcessorRegistry(state_manager=state_manager)

    for name, config in processors_config.items():
        if not config.get("enabled", True):
            continue

        processor_type = config.get("type")
        processor_config = config.get("config", {})

        # Add processor-level config
        processor_config.update(
            {"timeout": config.get("timeout", 300), "retry_attempts": config.get("retry_attempts", 3)}
        )

        try:
            registry.create_processor(name, processor_type, processor_config)
        except Exception as e:
            logger.error(f"Failed to create processor {name}: {e}")

    return registry
