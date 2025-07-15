"""Vault scanning functionality for Obsidian Post-Processor V2."""

import asyncio
import fnmatch
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import AsyncGenerator, List, Optional, Set

logger = logging.getLogger(__name__)


@dataclass
class NoteInfo:
    """Information about a note with potential voice attachments."""

    note_path: Path
    attachments: List[Path]
    modified_time: float
    size: int


class VaultScanner:
    """Async vault scanner with exclusion pattern support."""

    def __init__(self, vault_path: Path, exclude_patterns: List[str] = None):
        self.vault_path = vault_path
        self.exclude_patterns = exclude_patterns or []
        self.audio_extensions = {".m4a", ".mp3", ".wav", ".flac", ".aac", ".ogg", ".opus"}
        self.obsidian_attachment_folder = self._get_obsidian_attachment_folder()

    async def scan_vault(self) -> AsyncGenerator[NoteInfo, None]:
        """Scan vault for notes with voice attachments."""
        logger.info(f"Starting vault scan: {self.vault_path}")

        processed_files = 0
        found_notes = 0

        async for note_info in self._scan_notes():
            if await self._should_exclude(note_info.note_path):
                continue

            processed_files += 1

            # Check if note has voice attachments
            if note_info.attachments:
                found_notes += 1
                logger.debug(f"Found note with attachments: {note_info.note_path}")
                yield note_info

            # Yield control periodically
            if processed_files % 100 == 0:
                await asyncio.sleep(0)

        logger.info(f"Vault scan complete: {processed_files} files processed, {found_notes} notes with attachments")

    async def _scan_notes(self) -> AsyncGenerator[NoteInfo, None]:
        """Scan for markdown notes in the vault."""
        for note_path in self.vault_path.rglob("*.md"):
            if await self._should_exclude(note_path):
                continue

            try:
                stat = note_path.stat()
                attachments = await self._find_attachments(note_path)

                yield NoteInfo(
                    note_path=note_path, attachments=attachments, modified_time=stat.st_mtime, size=stat.st_size
                )

            except (OSError, IOError) as e:
                logger.warning(f"Error reading note {note_path}: {e}")
                continue

            # Yield control to other tasks
            await asyncio.sleep(0)

    async def _find_attachments(self, note_path: Path) -> List[Path]:
        """Find audio attachments referenced in the note."""
        attachments = []

        try:
            content = note_path.read_text(encoding="utf-8")
            attachment_paths = self._extract_attachment_paths(content)

            for attachment_path in attachment_paths:
                resolved_path = await self._resolve_attachment_path(note_path, attachment_path)
                if resolved_path and resolved_path.exists():
                    attachments.append(resolved_path)

        except (OSError, IOError, UnicodeDecodeError) as e:
            logger.warning(f"Error reading note content {note_path}: {e}")

        return attachments

    def _extract_attachment_paths(self, content: str) -> List[str]:
        """Extract attachment paths from note content."""
        import re

        # Pattern to match various attachment formats
        patterns = [
            r"!\[\[([^\]]+\.(m4a|mp3|wav|flac|aac|ogg|opus))\]\]",  # Obsidian wiki links
            r"!\[.*?\]\(([^\)]+\.(m4a|mp3|wav|flac|aac|ogg|opus))\)",  # Markdown links
            r'<audio[^>]*src=["\']([^"\']+\.(m4a|mp3|wav|flac|aac|ogg|opus))["\'][^>]*>',  # HTML audio tags
        ]

        attachment_paths = []
        for pattern in patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    attachment_paths.append(match[0])
                else:
                    attachment_paths.append(match)

        return attachment_paths

    def _get_obsidian_attachment_folder(self) -> Optional[str]:
        """Get the attachment folder path from Obsidian's app.json config."""
        try:
            app_json_path = self.vault_path / ".obsidian" / "app.json"
            if app_json_path.exists():
                with app_json_path.open("r", encoding="utf-8") as f:
                    config = json.load(f)
                    attachment_folder = config.get("attachmentFolderPath")
                    if attachment_folder:
                        logger.debug(f"Found Obsidian attachment folder: {attachment_folder}")
                        return attachment_folder
        except (OSError, IOError, json.JSONDecodeError) as e:
            logger.warning(f"Could not read Obsidian config: {e}")
        return None

    async def _resolve_attachment_path(self, note_path: Path, attachment_path: str) -> Optional[Path]:
        """Resolve attachment path relative to note and vault."""
        # Build candidate paths in order of priority
        candidates = [
            # Relative to note directory
            note_path.parent / attachment_path,
            # Relative to vault root
            self.vault_path / attachment_path,
        ]

        # Add Obsidian's configured attachment folder if available
        if self.obsidian_attachment_folder:
            candidates.append(self.vault_path / self.obsidian_attachment_folder / attachment_path)

        # Add common attachment directories
        candidates.extend(
            [
                self.vault_path / "Attachments" / attachment_path,
                self.vault_path / "attachments" / attachment_path,
                self.vault_path / "Files" / attachment_path,
                self.vault_path / "files" / attachment_path,
                # Direct path in vault
                self.vault_path / Path(attachment_path).name,
            ]
        )

        # Try each candidate
        for candidate in candidates:
            try:
                if candidate.exists() and candidate.suffix.lower() in self.audio_extensions:
                    logger.debug(f"Found attachment: {attachment_path} -> {candidate}")
                    return candidate.resolve()
                else:
                    logger.debug(f"Candidate not found or not audio: {candidate}")
            except (OSError, IOError) as e:
                logger.debug(f"Error checking candidate {candidate}: {e}")
                continue

        # Try case-insensitive search in common directories
        search_dirs = ["Attachments", "attachments", "Files", "files"]
        if self.obsidian_attachment_folder:
            search_dirs.insert(0, self.obsidian_attachment_folder)

        for dir_name in search_dirs:
            attachment_dir = self.vault_path / dir_name
            if attachment_dir.exists():
                logger.debug(f"Searching in directory: {attachment_dir}")
                try:
                    for file_path in attachment_dir.rglob("*"):
                        if (
                            file_path.name.lower() == Path(attachment_path).name.lower()
                            and file_path.suffix.lower() in self.audio_extensions
                        ):
                            logger.debug(f"Found attachment via search: {attachment_path} -> {file_path}")
                            return file_path
                except (OSError, IOError) as e:
                    logger.debug(f"Error searching in {attachment_dir}: {e}")
                    continue

        logger.warning(
            f"Could not resolve attachment: {attachment_path} (tried {len(candidates)} candidates and searched {len(search_dirs)} directories)"
        )
        return None

    async def _should_exclude(self, path: Path) -> bool:
        """Check if path should be excluded based on patterns."""
        try:
            # Get relative path from vault root
            rel_path = path.relative_to(self.vault_path)
            rel_path_str = str(rel_path)

            for pattern in self.exclude_patterns:
                if fnmatch.fnmatch(rel_path_str, pattern):
                    logger.debug(f"Excluding {path} (matches pattern: {pattern})")
                    return True

                # Also check if any parent directory matches
                for parent in rel_path.parents:
                    if fnmatch.fnmatch(str(parent), pattern):
                        logger.debug(f"Excluding {path} (parent matches pattern: {pattern})")
                        return True

            return False

        except ValueError:
            # Path is not relative to vault
            logger.warning(f"Path outside vault: {path}")
            return True

    async def get_vault_stats(self) -> dict:
        """Get statistics about the vault."""
        stats = {
            "total_notes": 0,
            "total_attachments": 0,
            "notes_with_attachments": 0,
            "excluded_notes": 0,
            "audio_extensions": list(self.audio_extensions),
            "exclude_patterns": self.exclude_patterns,
        }

        async for note_info in self._scan_notes():
            if await self._should_exclude(note_info.note_path):
                stats["excluded_notes"] += 1
                continue

            stats["total_notes"] += 1
            stats["total_attachments"] += len(note_info.attachments)

            if note_info.attachments:
                stats["notes_with_attachments"] += 1

        return stats

    async def find_note_by_path(self, note_path: Path) -> Optional[NoteInfo]:
        """Find specific note by path."""
        if not note_path.exists() or not note_path.suffix == ".md":
            return None

        if await self._should_exclude(note_path):
            return None

        try:
            stat = note_path.stat()
            attachments = await self._find_attachments(note_path)

            return NoteInfo(
                note_path=note_path, attachments=attachments, modified_time=stat.st_mtime, size=stat.st_size
            )

        except (OSError, IOError) as e:
            logger.warning(f"Error reading note {note_path}: {e}")
            return None


async def scan_vault_async(vault_path: Path, exclude_patterns: List[str] = None) -> List[NoteInfo]:
    """Convenience function to scan vault and return all notes."""
    scanner = VaultScanner(vault_path, exclude_patterns)
    notes = []

    async for note_info in scanner.scan_vault():
        notes.append(note_info)

    return notes
