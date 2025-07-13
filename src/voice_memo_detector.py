"""
Voice memo detector for Obsidian notes.

Uses obsidiantools to detect embedded voice recordings in markdown files.
"""

import json
import logging
import os
import re
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, List, Optional

import obsidiantools.api as otools

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


class VoiceMemoDetector:
    """Detects voice memos embedded in Obsidian notes."""

    def __init__(
        self,
        vault_path: Path,
        voice_patterns: List[str],
        suppress_frontmatter_errors: bool = False,
    ):
        self.vault_path = vault_path
        self.voice_patterns = voice_patterns
        self.vault = None
        self.suppress_frontmatter_errors = suppress_frontmatter_errors
        self._voice_extension_pattern = self._build_extension_pattern()
        self._obsidian_config = self._load_obsidian_config()

    def _build_extension_pattern(self) -> str:
        """Build regex pattern for voice file extensions."""
        extensions = []
        for pattern in self.voice_patterns:
            ext = pattern.replace("*", "").replace(".", "")
            extensions.append(ext)
        return "|".join(extensions)

    def _load_obsidian_config(self) -> Dict:
        """Load Obsidian configuration from .obsidian/app.json."""
        config_path = self.vault_path / ".obsidian" / "app.json"
        try:
            if config_path.exists():
                with open(config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    logger.debug(f"Loaded Obsidian config: {config}")
                    return config
            else:
                logger.debug(f"No Obsidian config found at {config_path}")
                return {}
        except Exception as e:
            logger.warning(f"Failed to load Obsidian config: {e}")
            return {}

    def _should_ignore_note(self, note_path: str) -> bool:
        """Check if a note should be ignored (e.g., template notes)."""
        # Since obsidiantools returns just the note name without directory,
        # we need to check the actual file path using metadata
        try:
            if self.vault:
                metadata = self.vault.get_all_file_metadata()
                if note_path in metadata.index:
                    rel_filepath = metadata.loc[note_path, "rel_filepath"]
                    rel_filepath_str = str(rel_filepath)

                    # Normalize path separators for cross-platform compatibility
                    normalized_path = rel_filepath_str.replace("\\", "/").lower()

                    # Check if in any templates directory (case-insensitive)
                    if (
                        normalized_path.startswith("templates/")
                        or "/templates/" in normalized_path
                    ):
                        logger.debug(
                            f"Ignoring template note: {note_path} (path: {rel_filepath})"
                        )
                        return True
                # Note: if note not found in metadata index, we don't ignore it
        except Exception as e:
            logger.debug(f"Error checking note path for {note_path}: {e}")

        return False

    def _get_attachment_folder_path(self) -> Optional[str]:
        """Get the attachment folder path from Obsidian configuration."""
        # Check if there's a specific attachment folder configured
        if "attachmentFolderPath" in self._obsidian_config:
            return self._obsidian_config["attachmentFolderPath"]

        # Check for legacy setting
        if "newFileLocation" in self._obsidian_config:
            location = self._obsidian_config["newFileLocation"]
            if location == "folder":
                return self._obsidian_config.get("newFileFolderPath", "attachments")

        # Default behavior
        return None

    def connect(self) -> "VoiceMemoDetector":
        """Connect to the Obsidian vault."""
        try:
            if self.suppress_frontmatter_errors:
                with suppress_frontmatter_errors():
                    self.vault = otools.Vault(self.vault_path).connect().gather()
            else:
                self.vault = otools.Vault(self.vault_path).connect().gather()
            logger.info(f"Connected to vault: {self.vault_path}")
            return self
        except Exception as e:
            logger.error(f"Failed to connect to vault {self.vault_path}: {e}")
            raise

    def get_notes_with_voice_memos(self) -> Dict[str, List[str]]:
        """
        Get all notes containing voice memos.

        Returns:
            Dict mapping note paths to lists of embedded voice file names.
        """
        if not self.vault:
            raise RuntimeError("Vault not connected. Call connect() first.")

        notes_with_memos = {}
        total_notes_scanned = 0
        notes_ignored = 0

        logger.debug(f"Starting voice memo detection in vault: {self.vault_path}")
        logger.debug(f"Voice extension pattern: {self._voice_extension_pattern}")
        logger.debug(f"Voice patterns: {self.voice_patterns}")

        try:
            if self.suppress_frontmatter_errors:
                with suppress_frontmatter_errors():
                    for note_path in self.vault.md_file_index:
                        total_notes_scanned += 1
                        logger.debug(f"Scanning note: {note_path}")

                        if self._should_ignore_note(note_path):
                            notes_ignored += 1
                            logger.debug(f"Ignoring note: {note_path}")
                            continue

                        voice_files = self._extract_voice_files_from_note(note_path)
                        if voice_files:
                            notes_with_memos[note_path] = voice_files
                            logger.debug(
                                f"Found {len(voice_files)} voice files in {note_path}: {voice_files}"
                            )
                        else:
                            logger.debug(f"No voice files found in {note_path}")
            else:
                for note_path in self.vault.md_file_index:
                    total_notes_scanned += 1
                    logger.debug(f"Scanning note: {note_path}")

                    if self._should_ignore_note(note_path):
                        notes_ignored += 1
                        logger.debug(f"Ignoring note: {note_path}")
                        continue

                    voice_files = self._extract_voice_files_from_note(note_path)
                    if voice_files:
                        notes_with_memos[note_path] = voice_files
                        logger.debug(
                            f"Found {len(voice_files)} voice files in {note_path}: {voice_files}"
                        )
                    else:
                        logger.debug(f"No voice files found in {note_path}")

        except Exception as e:
            logger.error(f"Error scanning vault for voice memos: {e}")
            raise

        logger.info(f"Voice memo detection complete: scanned {total_notes_scanned} notes, ignored {notes_ignored} notes, found {len(notes_with_memos)} notes with voice memos")

        if total_notes_scanned == 0:
            logger.warning("No notes found in vault - check vault path and .obsidian folder existence")
        elif len(notes_with_memos) == 0:
            logger.warning("No voice memos found - check voice file patterns and embedded audio syntax (![[filename.ext]])")

        return notes_with_memos

    def _extract_voice_files_from_note(self, note_path: str) -> List[str]:
        """
        Extract voice file names from a specific note.

        Args:
            note_path: Path to the note file

        Returns:
            List of voice file names found in the note
        """
        try:
            if self.suppress_frontmatter_errors:
                with suppress_frontmatter_errors():
                    source_text = self.vault.get_source_text(note_path)
            else:
                source_text = self.vault.get_source_text(note_path)

            if not source_text:
                logger.debug(f"No source text found for note: {note_path}")
                return []

            logger.debug(f"Extracting voice files from note: {note_path} (content length: {len(source_text)})")

            voice_files = []

            # Pattern to match Obsidian embedded files: ![[filename.ext]]
            embed_pattern = (
                r"!\[\[([^\]]+\.(?:" + self._voice_extension_pattern + r"))\]\]"
            )
            logger.debug(f"Using regex pattern: {embed_pattern}")

            # First, let's find ALL embedded files
            all_embeds_pattern = r"!\[\[([^\]]+)\]\]"
            all_embeds = re.findall(all_embeds_pattern, source_text, re.IGNORECASE)
            logger.debug(f"Found {len(all_embeds)} total embedded files in {note_path}: {all_embeds}")

            # Now find voice files specifically
            matches = re.findall(embed_pattern, source_text, re.IGNORECASE)
            logger.debug(f"Found {len(matches)} voice file matches in {note_path}: {matches}")

            for match in matches:
                voice_files.append(match)
                logger.debug(f"Added voice file: {match} from {note_path}")

            # Additional debug: show what patterns didn't match
            if all_embeds and not matches:
                non_matching = [e for e in all_embeds if not re.match(
                    r'.*\.(?:' + self._voice_extension_pattern + r')$', 
                    e, re.IGNORECASE)]
                logger.debug(f"Embedded files found but no voice files matched pattern. Non-matching embeds: {non_matching}")

            return voice_files

        except Exception as e:
            logger.error(f"Error extracting voice files from {note_path}: {e}")
            return []

    def get_voice_file_path(self, note_path: str, voice_filename: str) -> Path:
        """
        Get the full path to a voice file relative to the vault.

        Args:
            note_path: Path to the note containing the voice file
            voice_filename: Name of the voice file

        Returns:
            Full path to the voice file
        """
        # List of paths to try in order
        search_paths = []

        # 1. Try vault root first (most common case)
        search_paths.append(self.vault_path / voice_filename)

        # 2. Try configured attachment folder from Obsidian config
        configured_attachment_folder = self._get_attachment_folder_path()
        if configured_attachment_folder:
            search_paths.append(
                self.vault_path / configured_attachment_folder / voice_filename
            )

        # 3. Try same directory as the note (if note is in a subdirectory)
        note_dir = Path(note_path).parent
        if (
            str(note_dir) != "." and str(note_dir) != ""
        ):  # Only if note is actually in a subdirectory
            search_paths.append(self.vault_path / note_dir / voice_filename)

        # 4. Try to find voice file by searching the entire vault
        voice_path = self._find_voice_file_in_vault(voice_filename)
        if voice_path:
            search_paths.append(voice_path)

        # 5. Try common attachments folders
        for attachments_dir in ["attachments", "assets", "files", "media"]:
            search_paths.append(self.vault_path / attachments_dir / voice_filename)

        # Try each path and return the first one that exists
        for path in search_paths:
            if path.exists():
                logger.debug(f"Found voice file at: {path}")
                return path

        # If not found, return the most likely path (vault root)
        return self.vault_path / voice_filename

    def _find_voice_file_in_vault(self, voice_filename: str) -> Optional[Path]:
        """Search for a voice file throughout the vault directory structure."""
        try:
            # Use glob to find the file anywhere in the vault
            for path in self.vault_path.rglob(voice_filename):
                if path.is_file():
                    logger.debug(f"Found voice file by search: {path}")
                    return path
        except Exception as e:
            logger.debug(f"Error searching for voice file {voice_filename}: {e}")

        return None

    def verify_voice_files_exist(
        self, notes_with_memos: Dict[str, List[str]]
    ) -> Dict[str, List[str]]:
        """
        Verify that voice files actually exist on disk.

        Args:
            notes_with_memos: Dict mapping note paths to voice file names

        Returns:
            Dict with only existing voice files
        """
        verified_notes = {}

        for note_path, voice_files in notes_with_memos.items():
            existing_files = []

            for voice_file in voice_files:
                voice_path = self.get_voice_file_path(note_path, voice_file)
                if voice_path.exists():
                    existing_files.append(voice_file)
                    logger.debug(f"Verified voice file exists: {voice_path}")
                else:
                    logger.warning(
                        f"Voice file not found: {voice_file} for note {note_path}"
                    )
                    logger.warning(f"Voice file not found: {voice_path}")

            if existing_files:
                verified_notes[note_path] = existing_files

        return verified_notes
