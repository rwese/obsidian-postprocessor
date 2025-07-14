"""
Stateless state manager for tracking processed voice memos.

Manages state through frontmatter in Obsidian notes.
"""

import logging
import os
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import obsidiantools.api as otools
import yaml

logger = logging.getLogger(__name__)


@contextmanager
def suppress_frontmatter_errors():
    """Context manager to suppress frontmatter parsing errors from obsidiantools."""
    original_stderr = sys.stderr
    original_stdout = sys.stdout
    try:
        # Redirect both stdout and stderr to devnull to suppress error messages
        with open(os.devnull, "w") as devnull:
            sys.stderr = devnull
            sys.stdout = devnull
            yield
    finally:
        sys.stderr = original_stderr
        sys.stdout = original_stdout


class StatelessStateManager:
    """Manages processing state through frontmatter in Obsidian notes."""

    def __init__(self, vault_path: Path, frontmatter_error_level: str = "WARNING"):
        self.vault_path = vault_path
        self.vault = None
        self.frontmatter_error_level = frontmatter_error_level
        self.suppress_frontmatter_errors = frontmatter_error_level == "SILENT"

    def connect(self) -> "StatelessStateManager":
        """Connect to the Obsidian vault."""
        try:
            if self.suppress_frontmatter_errors:
                with suppress_frontmatter_errors():
                    self.vault = otools.Vault(self.vault_path).connect().gather()
            else:
                self.vault = otools.Vault(self.vault_path).connect().gather()
            logger.info(f"Connected to vault for state management: {self.vault_path}")
            return self
        except Exception as e:
            logger.error(f"Failed to connect to vault {self.vault_path}: {e}")
            raise

    def get_processed_recordings(self, note_path: str) -> List[str]:
        """
        Get list of processed recordings from note frontmatter.

        Args:
            note_path: Path to the note file

        Returns:
            List of processed recording filenames
        """
        if not self.vault:
            raise RuntimeError("Vault not connected. Call connect() first.")

        logger.debug(f"Getting processed recordings for note: {note_path}")

        try:
            if self.suppress_frontmatter_errors:
                with suppress_frontmatter_errors():
                    frontmatter = self.vault.get_front_matter(note_path)
            else:
                frontmatter = self.vault.get_front_matter(note_path)

            if not frontmatter:
                # Check if the note actually has frontmatter that failed to parse
                if self._has_malformed_frontmatter(note_path):
                    self._log_frontmatter_error(
                        f"Frontmatter parsing error in {note_path}: "
                        f"malformed YAML - continuing with empty processed list"
                    )
                logger.debug(f"No frontmatter found in {note_path}, returning empty processed list")
                return []

            processed = frontmatter.get("processed_recordings", [])
            if not isinstance(processed, list):
                self._log_frontmatter_error(
                    f"Invalid processed_recordings format in {note_path}, "
                    f"expected list, got {type(processed)} - "
                    f"continuing with empty processed list"
                )
                return []

            logger.debug(f"Found {len(processed)} processed recordings in {note_path}: {processed}")
            return processed

        except Exception as e:
            # Check if it's a YAML parsing error from obsidiantools
            if "ParserError" in str(e) or "while parsing" in str(e) or "yaml" in str(e).lower():
                self._log_frontmatter_error(
                    f"Frontmatter parsing error in {note_path}: {e} - continuing with empty processed list"
                )
                return []
            else:
                # For non-frontmatter errors, log as warning but continue processing
                logger.warning(
                    f"Error getting processed recordings from {note_path}: {e} - continuing with empty processed list"
                )
                return []

    def _has_malformed_frontmatter(self, note_path: str) -> bool:
        """Check if a note has malformed frontmatter by reading the file directly."""
        try:
            note_full_path = self.vault_path / f"{note_path}.md"
            if not note_full_path.exists():
                return False

            with open(note_full_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Check if it starts with frontmatter
            if not content.startswith("---"):
                return False

            # Try to parse it directly to see if it's malformed
            frontmatter, _ = self._parse_frontmatter(content)

            # If our parser succeeded but obsidiantools failed, it's likely malformed
            # This is a heuristic - if the content has frontmatter markers but obsidiantools
            # returned empty, it's probably malformed
            return content.startswith("---") and "---" in content[3:]

        except Exception:
            return False

    def _log_frontmatter_error(self, message: str):
        """Log frontmatter error at configured level."""
        if self.frontmatter_error_level == "SILENT":
            return
        elif self.frontmatter_error_level == "DEBUG":
            logger.debug(message)
        elif self.frontmatter_error_level == "INFO":
            logger.info(message)
        elif self.frontmatter_error_level == "WARNING":
            logger.warning(message)
        elif self.frontmatter_error_level == "ERROR":
            logger.error(message)
        elif self.frontmatter_error_level == "CRITICAL":
            logger.critical(message)

    def get_unprocessed_recordings(self, note_path: str, all_recordings: List[str]) -> List[str]:
        """
        Get list of unprocessed recordings by comparing with frontmatter.
        Excludes broken recordings from processing.

        Args:
            note_path: Path to the note file
            all_recordings: List of all voice recordings found in the note

        Returns:
            List of unprocessed recording filenames
        """
        processed = self.get_processed_recordings(note_path)
        broken = self.get_broken_recordings(note_path)

        # Exclude both processed and broken recordings
        unprocessed = [r for r in all_recordings if r not in processed and r not in broken]

        if unprocessed:
            logger.info(f"Found {len(unprocessed)} unprocessed recordings in {note_path}")
        if broken:
            logger.info(f"Skipping {len(broken)} broken recordings in {note_path}: {broken}")

        return unprocessed

    def mark_recording_processed(self, note_path: str, recording_filename: str) -> bool:
        """
        Mark a recording as processed by updating frontmatter.

        Args:
            note_path: Path to the note file (without .md extension)
            recording_filename: Name of the recording file

        Returns:
            True if successful, False otherwise
        """
        try:
            # Find the actual note file using robust path resolution
            note_full_path = self._find_note_file(note_path)
            if not note_full_path:
                logger.error(f"Note file not found: {note_path} (searched in vault {self.vault_path})")
                return False

            with open(note_full_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Parse frontmatter and content
            frontmatter, body = self._parse_frontmatter(content)

            # Update processed recordings list
            if "processed_recordings" not in frontmatter:
                frontmatter["processed_recordings"] = []

            if recording_filename not in frontmatter["processed_recordings"]:
                frontmatter["processed_recordings"].append(recording_filename)
                frontmatter["processed_recordings"].sort()  # Keep sorted for consistency

            # Write back to file
            new_content = self._serialize_frontmatter(frontmatter, body)

            with open(note_full_path, "w", encoding="utf-8") as f:
                f.write(new_content)

            logger.info(f"Marked recording as processed: {recording_filename} in {note_path}")

            # Reload the vault to pick up the changes
            if self.suppress_frontmatter_errors:
                with suppress_frontmatter_errors():
                    self.vault = otools.Vault(self.vault_path).connect().gather()
            else:
                self.vault = otools.Vault(self.vault_path).connect().gather()

            return True

        except Exception as e:
            logger.error(f"Error marking recording as processed: {e}")
            return False

    def _parse_frontmatter(self, content: str) -> tuple:
        """
        Parse frontmatter from note content.

        Args:
            content: Raw note content

        Returns:
            Tuple of (frontmatter dict, body content)
        """
        if not content.startswith("---"):
            # No frontmatter, return empty dict and full content
            return {}, content

        try:
            # Find the end of frontmatter
            lines = content.split("\n")
            end_idx = -1

            for i, line in enumerate(lines[1:], 1):
                if line.strip() == "---":
                    end_idx = i
                    break

            if end_idx == -1:
                # No closing ---, treat as no frontmatter
                logger.warning("Frontmatter opening found but no closing '---', treating as regular content")
                return {}, content

            # Extract and parse frontmatter
            frontmatter_text = "\n".join(lines[1:end_idx])
            body = "\n".join(lines[end_idx + 1 :])

            if not frontmatter_text.strip():
                # Empty frontmatter
                return {}, body

            # Try to parse YAML with better error handling
            try:
                frontmatter = yaml.safe_load(frontmatter_text)
                if frontmatter is None:
                    frontmatter = {}
                elif not isinstance(frontmatter, dict):
                    self._log_frontmatter_error(
                        f"Frontmatter is not a dictionary, got {type(frontmatter)}, treating as empty"
                    )
                    frontmatter = {}
            except yaml.YAMLError as yaml_error:
                self._log_frontmatter_error(f"Invalid YAML frontmatter, treating as empty: {yaml_error}")
                frontmatter = {}

            return frontmatter, body

        except Exception as e:
            logger.error(f"Unexpected error parsing frontmatter: {e}")
            return {}, content

    def _serialize_frontmatter(self, frontmatter: Dict[str, Any], body: str) -> str:
        """
        Serialize frontmatter and body back to note content.

        Args:
            frontmatter: Frontmatter dictionary
            body: Note body content

        Returns:
            Complete note content with frontmatter
        """
        if not frontmatter:
            return body

        try:
            # Serialize frontmatter to YAML
            yaml_content = yaml.dump(frontmatter, default_flow_style=False, allow_unicode=True)

            # Ensure body starts with newline if it exists
            if body and not body.startswith("\n"):
                body = "\n" + body

            return f"---\n{yaml_content}---{body}"

        except Exception as e:
            logger.error(f"Error serializing frontmatter: {e}")
            return body

    def get_processing_stats(self, notes_with_memos: Dict[str, List[str]]) -> Dict[str, int]:
        """
        Get processing statistics for all notes.

        Args:
            notes_with_memos: Dict mapping note paths to voice file lists

        Returns:
            Dictionary with processing statistics
        """
        stats = {
            "total_notes": len(notes_with_memos),
            "total_recordings": 0,
            "processed_recordings": 0,
            "broken_recordings": 0,
            "unprocessed_recordings": 0,
        }

        for note_path, recordings in notes_with_memos.items():
            stats["total_recordings"] += len(recordings)
            processed = self.get_processed_recordings(note_path)
            broken = self.get_broken_recordings(note_path)
            stats["processed_recordings"] += len(processed)
            stats["broken_recordings"] += len(broken)
            unprocessed = self.get_unprocessed_recordings(note_path, recordings)
            stats["unprocessed_recordings"] += len(unprocessed)

        return stats

    def _find_note_file(self, note_path: str) -> Optional[Path]:
        """
        Find a note file using robust path resolution similar to voice file detection.

        Args:
            note_path: Path to the note (without .md extension)

        Returns:
            Full path to the note file if found, None otherwise
        """
        # List of paths to try in order
        search_paths = []

        # 1. Try vault root first (most common case)
        search_paths.append(self.vault_path / f"{note_path}.md")

        # 2. Try with the note_path as-is if it already has .md extension
        if not note_path.endswith(".md"):
            search_paths.append(self.vault_path / note_path)
        else:
            # Remove .md and try again
            note_without_ext = note_path[:-3]
            search_paths.append(self.vault_path / f"{note_without_ext}.md")

        # 3. Try to find note file by searching the entire vault
        note_file = self._find_note_file_in_vault(note_path)
        if note_file:
            search_paths.append(note_file)

        # 4. Try common subdirectories
        for subdir in [
            "Notes",
            "notes",
            "Pages",
            "pages",
            "Daily Notes",
            "Templates",
        ]:
            search_paths.append(self.vault_path / subdir / f"{note_path}.md")

        # Try each path and return the first one that exists
        for path in search_paths:
            if path.exists() and path.is_file():
                logger.debug(f"Found note file at: {path}")
                return path

        return None

    def _find_note_file_in_vault(self, note_path: str) -> Optional[Path]:
        """Search for a note file throughout the vault directory structure."""
        try:
            # Remove .md extension if present for searching
            note_name = note_path.replace(".md", "")

            # Use glob to find the file anywhere in the vault
            for pattern in [
                f"{note_name}.md",
                f"*/{note_name}.md",
                f"**/{note_name}.md",
            ]:
                for path in self.vault_path.glob(pattern):
                    if path.is_file():
                        logger.debug(f"Found note file by search: {path}")
                        return path

            # Also try recursive search with rglob
            for path in self.vault_path.rglob(f"{note_name}.md"):
                if path.is_file():
                    logger.debug(f"Found note file by recursive search: {path}")
                    return path

        except Exception as e:
            logger.debug(f"Error searching for note file {note_path}: {e}")

        return None

    def get_broken_recordings(self, note_path: str) -> List[str]:
        """
        Get list of broken recordings from note frontmatter.

        Args:
            note_path: Path to the note file

        Returns:
            List of broken recording filenames
        """
        if not self.vault:
            raise RuntimeError("Vault not connected. Call connect() first.")

        logger.debug(f"Getting broken recordings for note: {note_path}")

        try:
            if self.suppress_frontmatter_errors:
                with suppress_frontmatter_errors():
                    frontmatter = self.vault.get_front_matter(note_path)
            else:
                frontmatter = self.vault.get_front_matter(note_path)

            if not frontmatter:
                logger.debug(f"No frontmatter found in {note_path}, returning empty broken list")
                return []

            broken = frontmatter.get("broken_recordings", [])
            if not isinstance(broken, list):
                self._log_frontmatter_error(
                    f"Invalid broken_recordings format in {note_path}, "
                    f"expected list, got {type(broken)} - "
                    f"continuing with empty broken list"
                )
                return []

            logger.debug(f"Found {len(broken)} broken recordings in {note_path}: {broken}")
            return broken

        except Exception as e:
            if "ParserError" in str(e) or "while parsing" in str(e) or "yaml" in str(e).lower():
                self._log_frontmatter_error(
                    f"Frontmatter parsing error in {note_path}: {e} - continuing with empty broken list"
                )
                return []
            else:
                # For non-frontmatter errors, log as warning but continue processing
                logger.warning(
                    f"Error getting broken recordings from {note_path}: {e} - continuing with empty broken list"
                )
                return []

    def mark_recording_broken(
        self,
        note_path: str,
        recording_filename: str,
        error_message: str = None,
    ) -> bool:
        """
        Mark a recording as broken by updating frontmatter.

        Args:
            note_path: Path to the note file (without .md extension)
            recording_filename: Name of the recording file
            error_message: Optional error message to include

        Returns:
            True if successful, False otherwise
        """
        try:
            # Find the actual note file using robust path resolution
            note_full_path = self._find_note_file(note_path)
            if not note_full_path:
                logger.error(f"Note file not found: {note_path} (searched in vault {self.vault_path})")
                return False

            with open(note_full_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Parse frontmatter and content
            frontmatter, body = self._parse_frontmatter(content)

            # Update broken recordings list
            if "broken_recordings" not in frontmatter:
                frontmatter["broken_recordings"] = []

            if recording_filename not in frontmatter["broken_recordings"]:
                frontmatter["broken_recordings"].append(recording_filename)
                frontmatter["broken_recordings"].sort()  # Keep sorted for consistency

            # Add error timestamp and message if provided
            if error_message:
                if "broken_recordings_info" not in frontmatter:
                    frontmatter["broken_recordings_info"] = {}

                from datetime import datetime

                timestamp = datetime.now().isoformat()
                frontmatter["broken_recordings_info"][recording_filename] = {
                    "error": error_message,
                    "timestamp": timestamp,
                }

            # Write back to file
            new_content = self._serialize_frontmatter(frontmatter, body)

            with open(note_full_path, "w", encoding="utf-8") as f:
                f.write(new_content)

            logger.warning(
                f"Marked recording as broken: {recording_filename} in {note_path}"
                + (f" - {error_message}" if error_message else "")
            )

            # Reload the vault to pick up the changes
            if self.suppress_frontmatter_errors:
                with suppress_frontmatter_errors():
                    self.vault = otools.Vault(self.vault_path).connect().gather()
            else:
                self.vault = otools.Vault(self.vault_path).connect().gather()

            return True

        except Exception as e:
            logger.error(f"Error marking recording as broken: {e}")
            return False

    # New improved frontmatter structure methods

    def _get_postprocessor_metadata(self, note_path: str) -> Dict[str, Any]:
        """Get obsidian-postprocessor metadata from frontmatter."""
        try:
            if not self.vault:
                return {}

            frontmatter = self._get_frontmatter(note_path)
            return frontmatter.get("obsidian-postprocessor", {})

        except Exception as e:
            logger.debug(f"Error getting postprocessor metadata from {note_path}: {e}")
            return {}

    def _update_voice_memo_status(self, note_path: str, voice_filename: str, status: str, **metadata) -> bool:
        """
        Update voice memo status in the new frontmatter structure.

        Args:
            note_path: Path to the note
            voice_filename: Name of the voice file
            status: Status (pending, processing, processed, failed, broken)
            **metadata: Additional metadata like error, transcript_length, model, etc.
        """
        try:
            note_full_path = self._find_note_file(note_path)
            if not note_full_path:
                logger.error(f"Note file not found: {note_path}")
                return False

            # Read current content
            with open(note_full_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Parse frontmatter and content
            frontmatter, body = self._parse_frontmatter(content)

            # Initialize obsidian-postprocessor structure if needed
            if "obsidian-postprocessor" not in frontmatter:
                frontmatter["obsidian-postprocessor"] = {"version": "1.0", "voice-memos": {}}

            postprocessor = frontmatter["obsidian-postprocessor"]

            # Ensure voice-memos section exists
            if "voice-memos" not in postprocessor:
                postprocessor["voice-memos"] = {}

            # Update voice memo entry
            voice_memo_data = {"status": status, "updated_at": datetime.now(timezone.utc).isoformat()}

            # Add additional metadata
            voice_memo_data.update(metadata)

            postprocessor["voice-memos"][voice_filename] = voice_memo_data

            # Maintain backward compatibility - update legacy processed_recordings list
            if status == "processed":
                if "processed_recordings" not in frontmatter:
                    frontmatter["processed_recordings"] = []
                if voice_filename not in frontmatter["processed_recordings"]:
                    frontmatter["processed_recordings"].append(voice_filename)
                    frontmatter["processed_recordings"].sort()

            # Write back to file
            new_content = self._serialize_frontmatter(frontmatter, body)

            with open(note_full_path, "w", encoding="utf-8") as f:
                f.write(new_content)

            logger.info(f"Updated voice memo status: {voice_filename} -> {status} in {note_path}")

            # Reload the vault to pick up the changes
            if self.suppress_frontmatter_errors:
                with suppress_frontmatter_errors():
                    self.vault = otools.Vault(self.vault_path).connect(attachments=True).gather()
            else:
                self.vault = otools.Vault(self.vault_path).connect(attachments=True).gather()

            return True

        except Exception as e:
            logger.error(f"Error updating voice memo status: {e}")
            return False

    def get_voice_memo_status(self, note_path: str, voice_filename: str) -> Optional[Dict[str, Any]]:
        """Get detailed status for a specific voice memo."""
        try:
            postprocessor_data = self._get_postprocessor_metadata(note_path)
            voice_memos = postprocessor_data.get("voice-memos", {})
            return voice_memos.get(voice_filename)

        except Exception as e:
            logger.debug(f"Error getting voice memo status: {e}")
            return None

    def mark_recording_as_processed_enhanced(
        self,
        note_path: str,
        recording_filename: str,
        transcript_length: Optional[int] = None,
        model: Optional[str] = None,
        language: Optional[str] = None,
    ) -> bool:
        """Mark recording as processed with enhanced metadata."""
        metadata = {}
        if transcript_length is not None:
            metadata["transcript_length"] = transcript_length
        if model:
            metadata["model"] = model
        if language:
            metadata["language"] = language

        return self._update_voice_memo_status(note_path, recording_filename, "processed", **metadata)

    def mark_recording_as_failed_enhanced(
        self, note_path: str, recording_filename: str, error_message: str, retry_count: int = 0
    ) -> bool:
        """Mark recording as failed with error details."""
        return self._update_voice_memo_status(
            note_path, recording_filename, "failed", error=error_message, retries=retry_count
        )

    def mark_recording_as_pending(self, note_path: str, recording_filename: str) -> bool:
        """Mark recording as pending processing."""
        return self._update_voice_memo_status(note_path, recording_filename, "pending")

    def clear_broken_recordings(self, note_path: str) -> bool:
        """
        Clear all broken recordings from a note, allowing them to be reprocessed.

        Args:
            note_path: Path to the note file

        Returns:
            True if successful, False otherwise
        """
        try:
            note_full_path = self._find_note_file(note_path)
            if not note_full_path:
                logger.error(f"Note file not found: {note_path}")
                return False

            # Read current content
            with open(note_full_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Parse frontmatter and content
            frontmatter, body = self._parse_frontmatter(content)

            # Clear legacy broken recordings
            if "broken_recordings" in frontmatter:
                broken_count = len(frontmatter["broken_recordings"])
                frontmatter["broken_recordings"] = []
                logger.info(f"Cleared {broken_count} broken recordings from legacy list in {note_path}")

            if "broken_recordings_info" in frontmatter:
                frontmatter["broken_recordings_info"] = {}
                logger.info(f"Cleared broken recordings info from legacy list in {note_path}")

            # Clear enhanced broken recordings
            if "obsidian-postprocessor" in frontmatter:
                postprocessor = frontmatter["obsidian-postprocessor"]
                if "voice-memos" in postprocessor:
                    voice_memos = postprocessor["voice-memos"]
                    # Remove all recordings with "failed" or "broken" status
                    cleared_files = []
                    for filename, data in list(voice_memos.items()):
                        if data.get("status") in ["failed", "broken"]:
                            cleared_files.append(filename)
                            del voice_memos[filename]

                    if cleared_files:
                        logger.info(
                            f"Cleared {len(cleared_files)} broken recordings from enhanced tracking in {note_path}"
                        )

            # Write back to file
            new_content = self._serialize_frontmatter(frontmatter, body)

            with open(note_full_path, "w", encoding="utf-8") as f:
                f.write(new_content)

            logger.info(f"Successfully cleared broken recordings from {note_path}")

            # Reload the vault to pick up the changes
            if self.suppress_frontmatter_errors:
                with suppress_frontmatter_errors():
                    self.vault = otools.Vault(self.vault_path).connect(attachments=True).gather()
            else:
                self.vault = otools.Vault(self.vault_path).connect(attachments=True).gather()

            return True

        except Exception as e:
            logger.error(f"Error clearing broken recordings: {e}")
            return False
