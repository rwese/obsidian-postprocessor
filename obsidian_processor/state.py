"""State management system for Obsidian Post-Processor V2."""

import asyncio
import logging
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from .parser import FrontmatterParser
from .processors import ProcessResult

logger = logging.getLogger(__name__)


class ProcessingStatus(Enum):
    """Processing status values."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class ProcessingState:
    """State information for a processor."""

    status: ProcessingStatus
    timestamp: float
    message: Optional[str] = None
    output: Optional[str] = None
    error: Optional[str] = None
    retry_count: int = 0
    processing_time: float = 0.0


class StateManager:
    """Manages processing state in note frontmatter."""

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.parser = FrontmatterParser()
        self._lock = asyncio.Lock()

    async def get_processing_state(self, note_path: Path) -> Dict[str, ProcessingState]:
        """Get current processing state for a note."""
        try:
            parsed_note = await self.parser.parse_note(note_path)
            processor_state = self.parser.get_processing_state(parsed_note.frontmatter)

            states = {}
            for processor_name, state_data in processor_state.items():
                if isinstance(state_data, dict):
                    states[processor_name] = ProcessingState(
                        status=ProcessingStatus(state_data.get("status", "pending")),
                        timestamp=state_data.get("timestamp", time.time()),
                        message=state_data.get("message"),
                        output=state_data.get("output"),
                        error=state_data.get("error"),
                        retry_count=state_data.get("retry_count", 0),
                        processing_time=state_data.get("processing_time", 0.0),
                    )
                else:
                    # Handle legacy string-based state
                    states[processor_name] = ProcessingState(
                        status=(
                            ProcessingStatus(state_data) if isinstance(state_data, str) else ProcessingStatus.PENDING
                        ),
                        timestamp=time.time(),
                    )

            return states

        except Exception as e:
            logger.error(f"Error getting processing state for {note_path}: {e}")
            return {}

    async def update_processing_state(self, note_path: Path, processor_name: str, state: ProcessingState):
        """Update processing state for a specific processor."""
        if self.dry_run:
            logger.info(f"DRY RUN: Would update state for {processor_name} in {note_path}")
            return

        async with self._lock:
            try:
                await self._update_state_atomic(note_path, processor_name, state)
            except Exception as e:
                logger.error(f"Error updating processing state for {note_path}: {e}")
                raise

    async def _update_state_atomic(self, note_path: Path, processor_name: str, state: ProcessingState):
        """Atomically update processing state in frontmatter."""
        # Read current content
        content = note_path.read_text(encoding="utf-8")

        # Parse current frontmatter
        parsed_note = await self.parser.parse_note(note_path)
        frontmatter = parsed_note.frontmatter.copy()

        # Update processor state
        if "processor_state" not in frontmatter:
            frontmatter["processor_state"] = {}

        frontmatter["processor_state"][processor_name] = {
            "status": state.status.value,
            "timestamp": state.timestamp,
            "message": state.message,
            "output": state.output,
            "error": state.error,
            "retry_count": state.retry_count,
            "processing_time": state.processing_time,
        }

        # Remove None values to keep frontmatter clean
        frontmatter["processor_state"][processor_name] = {
            k: v for k, v in frontmatter["processor_state"][processor_name].items() if v is not None
        }

        # Update content with new frontmatter
        new_content = self._update_content_frontmatter(content, frontmatter)

        # Write atomically
        await self._write_file_atomic(note_path, new_content)

    def _update_content_frontmatter(self, content: str, frontmatter: Dict[str, Any]) -> str:
        """Update frontmatter in note content."""
        # Convert frontmatter to YAML
        yaml_content = yaml.dump(frontmatter, default_flow_style=False, allow_unicode=True)

        # Check if content already has frontmatter
        if content.startswith("---\n"):
            # Find end of existing frontmatter
            lines = content.split("\n")
            end_index = -1
            for i, line in enumerate(lines[1:], 1):
                if line.strip() == "---":
                    end_index = i
                    break

            if end_index > 0:
                # Replace existing frontmatter
                body = "\n".join(lines[end_index + 1 :])
                return f"---\n{yaml_content}---\n{body}"

        # Add new frontmatter
        return f"---\n{yaml_content}---\n{content}"

    async def _write_file_atomic(self, file_path: Path, content: str):
        """Write file atomically to prevent corruption."""
        temp_path = file_path.with_suffix(f"{file_path.suffix}.tmp")

        try:
            # Write to temporary file
            temp_path.write_text(content, encoding="utf-8")

            # Atomic rename
            temp_path.replace(file_path)

        except Exception as e:
            # Clean up temp file on error
            if temp_path.exists():
                temp_path.unlink()
            raise e

    async def mark_processing_start(self, note_path: Path, processor_name: str):
        """Mark processor as starting."""
        state = ProcessingState(status=ProcessingStatus.PROCESSING, timestamp=time.time(), message="Processing started")
        await self.update_processing_state(note_path, processor_name, state)

    async def mark_processing_complete(self, note_path: Path, processor_name: str, result: ProcessResult):
        """Mark processor as complete with result."""
        state = ProcessingState(
            status=ProcessingStatus.COMPLETED if result.success else ProcessingStatus.FAILED,
            timestamp=time.time(),
            message=result.message,
            output=result.output,
            error=result.error,
            retry_count=result.retry_count,
            processing_time=result.processing_time,
        )
        await self.update_processing_state(note_path, processor_name, state)

        # Clean up legacy failure tracking fields if processing succeeds
        if result.success:
            await self._cleanup_legacy_failure_fields(note_path, processor_name)

    async def mark_processing_skipped(self, note_path: Path, processor_name: str, reason: str):
        """Mark processor as skipped."""
        state = ProcessingState(status=ProcessingStatus.SKIPPED, timestamp=time.time(), message=reason)
        await self.update_processing_state(note_path, processor_name, state)

    async def should_process(self, note_path: Path, processor_name: str) -> bool:
        """Determine if processor should run for this note."""
        states = await self.get_processing_state(note_path)

        if processor_name not in states:
            return True

        state = states[processor_name]

        # Process if pending or failed
        return state.status in [ProcessingStatus.PENDING, ProcessingStatus.FAILED]

    async def get_processing_summary(self, note_path: Path) -> Dict[str, Any]:
        """Get summary of processing states for a note."""
        states = await self.get_processing_state(note_path)

        summary = {
            "total_processors": len(states),
            "completed": 0,
            "failed": 0,
            "pending": 0,
            "processing": 0,
            "skipped": 0,
            "processors": {},
        }

        for processor_name, state in states.items():
            summary["processors"][processor_name] = {
                "status": state.status.value,
                "timestamp": state.timestamp,
                "message": state.message,
                "processing_time": state.processing_time,
            }

            # Count by status
            if state.status == ProcessingStatus.COMPLETED:
                summary["completed"] += 1
            elif state.status == ProcessingStatus.FAILED:
                summary["failed"] += 1
            elif state.status == ProcessingStatus.PENDING:
                summary["pending"] += 1
            elif state.status == ProcessingStatus.PROCESSING:
                summary["processing"] += 1
            elif state.status == ProcessingStatus.SKIPPED:
                summary["skipped"] += 1

        return summary

    async def reset_processor_state(self, note_path: Path, processor_name: str):
        """Reset state for a specific processor."""
        state = ProcessingState(status=ProcessingStatus.PENDING, timestamp=time.time(), message="State reset")
        await self.update_processing_state(note_path, processor_name, state)

    async def _cleanup_legacy_failure_fields(self, note_path: Path, processor_name: str):
        """Remove legacy failure tracking fields when processing succeeds."""
        if self.dry_run:
            logger.info(f"DRY RUN: Would cleanup legacy failure fields in {note_path}")
            return

        async with self._lock:
            parsed_note = await self.parser.parse_note(note_path)
            frontmatter = parsed_note.frontmatter.copy()

            # Legacy fields to remove based on processor type
            fields_to_remove = []

            if processor_name == "transcribe":
                fields_to_remove.extend(
                    ["broken_recordings", "broken_recordings_info", "obsidian-postprocessor"]  # Old v1 field
                )

            # Remove legacy fields
            removed_fields = []
            for field in fields_to_remove:
                if field in frontmatter:
                    frontmatter.pop(field)
                    removed_fields.append(field)

            # Update content if we removed any fields
            if removed_fields:
                content = note_path.read_text(encoding="utf-8")
                new_content = self._update_content_frontmatter(content, frontmatter)
                await self._write_file_atomic(note_path, new_content)
                logger.info(f"Cleaned up legacy failure fields {removed_fields} from {note_path}")

    async def cleanup_old_states(self, note_path: Path, max_age_days: int = 30):
        """Remove old processing states."""
        if self.dry_run:
            logger.info(f"DRY RUN: Would cleanup old states in {note_path}")
            return

        cutoff_time = time.time() - (max_age_days * 24 * 60 * 60)
        states = await self.get_processing_state(note_path)

        states_to_remove = []
        for processor_name, state in states.items():
            if state.timestamp < cutoff_time and state.status in [ProcessingStatus.COMPLETED, ProcessingStatus.FAILED]:
                states_to_remove.append(processor_name)

        if states_to_remove:
            async with self._lock:
                parsed_note = await self.parser.parse_note(note_path)
                frontmatter = parsed_note.frontmatter.copy()

                if "processor_state" in frontmatter:
                    for processor_name in states_to_remove:
                        frontmatter["processor_state"].pop(processor_name, None)

                    # Remove empty processor_state
                    if not frontmatter["processor_state"]:
                        frontmatter.pop("processor_state", None)

                    # Update content
                    content = note_path.read_text(encoding="utf-8")
                    new_content = self._update_content_frontmatter(content, frontmatter)
                    await self._write_file_atomic(note_path, new_content)

                    logger.info(f"Cleaned up {len(states_to_remove)} old states from {note_path}")

    async def get_vault_processing_stats(self, vault_path: Path) -> Dict[str, Any]:
        """Get processing statistics for entire vault."""
        stats = {
            "total_notes": 0,
            "notes_with_state": 0,
            "total_processors": 0,
            "completed": 0,
            "failed": 0,
            "pending": 0,
            "processing": 0,
            "skipped": 0,
            "processors": {},
        }

        for note_path in vault_path.rglob("*.md"):
            if not note_path.is_file():
                continue

            stats["total_notes"] += 1

            try:
                states = await self.get_processing_state(note_path)
                if states:
                    stats["notes_with_state"] += 1

                    for processor_name, state in states.items():
                        stats["total_processors"] += 1

                        if processor_name not in stats["processors"]:
                            stats["processors"][processor_name] = {
                                "completed": 0,
                                "failed": 0,
                                "pending": 0,
                                "processing": 0,
                                "skipped": 0,
                            }

                        stats["processors"][processor_name][state.status.value] += 1
                        stats[state.status.value] += 1

            except Exception as e:
                logger.warning(f"Error getting state for {note_path}: {e}")

        return stats
