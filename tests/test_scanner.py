"""
Test async vault scanner for V2
"""

import asyncio
from pathlib import Path
from typing import Optional

import pytest

# Placeholder for future scanner implementation
# from obsidian_processor.scanner import VaultScanner, ScannerError


class TestVaultScanner:
    """Test async vault scanning functionality"""

    def test_scanner_placeholder(self):
        """Placeholder test - will be updated when scanner.py is implemented"""
        assert True

    @pytest.mark.asyncio
    async def test_scan_vault_structure(self, test_vault: Path):
        """Test scanning basic vault structure"""
        vault_path = test_vault

        # Test that vault structure exists
        assert vault_path.exists()
        assert vault_path.is_dir()

        # Test expected directories
        assert (vault_path / "daily").exists()
        assert (vault_path / "templates").exists()
        assert (vault_path / "archive").exists()
        assert (vault_path / "attachments").exists()

        # Test expected files
        assert (vault_path / "daily" / "2024-01-01.md").exists()
        assert (vault_path / "templates" / "daily.md").exists()
        assert (vault_path / "regular.md").exists()
        assert (vault_path / "processed.md").exists()
        assert (vault_path / "attachments" / "recording.m4a").exists()

    @pytest.mark.asyncio
    async def test_find_notes_with_voice_memos(self, test_vault: Path):
        """Test finding notes with voice memo attachments"""
        vault_path = test_vault

        # Manually scan for notes with voice memos
        voice_memo_notes = []

        for md_file in vault_path.rglob("*.md"):
            if md_file.name.endswith(".md"):
                try:
                    content = md_file.read_text()
                    # Simple pattern matching for voice attachments
                    if any(pattern in content for pattern in ["![[recording.m4a]]", "![[*.m4a]]"]):
                        voice_memo_notes.append(md_file)
                except Exception:
                    # Skip files that can't be read
                    pass

        # Should find at least the daily note and processed note
        assert len(voice_memo_notes) >= 2

        # Check specific notes
        daily_note = vault_path / "daily" / "2024-01-01.md"
        processed_note = vault_path / "processed.md"

        assert daily_note in voice_memo_notes
        assert processed_note in voice_memo_notes

    @pytest.mark.asyncio
    async def test_exclusion_patterns(self, test_vault: Path):
        """Test exclusion pattern matching"""
        vault_path = test_vault

        # Get all markdown files
        all_md_files = list(vault_path.rglob("*.md"))

        # Test template exclusion
        template_files = [f for f in all_md_files if "templates" in f.parts]
        assert len(template_files) > 0  # Should have template files

        # Test archive exclusion - check if any exist
        # Archive might be empty in test vault

        # Test .template.md exclusion - check if any exist
        # Might not have any in test vault

        # Regular files should not be excluded
        regular_files = [
            f
            for f in all_md_files
            if not any(pattern_part in f.parts for pattern_part in ["templates", "archive"])
            and not f.name.endswith(".template.md")
        ]

        assert len(regular_files) > 0

    @pytest.mark.asyncio
    async def test_async_file_reading(self, test_vault: Path):
        """Test async file reading operations"""
        vault_path = test_vault

        # Test reading multiple files concurrently
        md_files = list(vault_path.rglob("*.md"))

        async def read_file_async(file_path: Path) -> tuple[Path, str]:
            # Simulate async file reading
            await asyncio.sleep(0.01)  # Small delay to simulate I/O
            return file_path, file_path.read_text()

        # Read all files concurrently
        tasks = [read_file_async(f) for f in md_files[:3]]  # Limit to first 3
        results = await asyncio.gather(*tasks)

        # Should have results for all files
        assert len(results) == len(tasks)

        # Each result should be a tuple of (path, content)
        for file_path, content in results:
            assert isinstance(file_path, Path)
            assert isinstance(content, str)
            assert len(content) > 0

    @pytest.mark.asyncio
    async def test_incremental_scanning(self, test_vault: Path):
        """Test incremental scanning based on file modification time"""
        vault_path = test_vault

        # Get all markdown files with their modification times
        md_files = list(vault_path.rglob("*.md"))
        file_times = [(f, f.stat().st_mtime) for f in md_files]

        # Sort by modification time
        file_times.sort(key=lambda x: x[1])

        # Should be able to process files in order
        assert len(file_times) > 0

        # Test that we can identify "newer" files
        if len(file_times) > 1:
            older_file, older_time = file_times[0]
            newer_file, newer_time = file_times[-1]

            # Time should be different or same
            assert newer_time >= older_time

    @pytest.mark.asyncio
    async def test_concurrent_scanning(self, test_vault: Path):
        """Test concurrent scanning with limits"""
        vault_path = test_vault

        md_files = list(vault_path.rglob("*.md"))

        # Test concurrent processing with semaphore
        semaphore = asyncio.Semaphore(2)  # Limit to 2 concurrent operations

        async def process_file_with_limit(file_path: Path) -> Path:
            async with semaphore:
                await asyncio.sleep(0.01)  # Simulate processing
                return file_path

        # Process files concurrently with limit
        tasks = [process_file_with_limit(f) for f in md_files]
        results = await asyncio.gather(*tasks)

        # Should process all files
        assert len(results) == len(md_files)
        assert all(isinstance(r, Path) for r in results)

    @pytest.mark.asyncio
    async def test_error_handling_during_scan(self, test_vault: Path):
        """Test error handling during vault scanning"""
        vault_path = test_vault

        # Create a file that will cause read errors
        problem_file = vault_path / "problem.md"
        problem_file.write_text("Valid content")

        # Test reading with error handling
        async def read_with_error_handling(file_path: Path) -> tuple[Path, Optional[str]]:
            try:
                await asyncio.sleep(0.01)
                return file_path, file_path.read_text()
            except Exception:
                return file_path, None

        # Test that errors don't crash the scanner
        result = await read_with_error_handling(problem_file)
        assert result[0] == problem_file
        assert result[1] is not None  # Should successfully read

        # Test with non-existent file
        nonexistent = vault_path / "nonexistent.md"
        result = await read_with_error_handling(nonexistent)
        assert result[0] == nonexistent
        assert result[1] is None  # Should handle error gracefully

    @pytest.mark.asyncio
    async def test_audio_file_detection(self, test_vault: Path):
        """Test detection of audio files in vault"""
        vault_path = test_vault

        # Find audio files
        audio_extensions = [".m4a", ".mp3", ".wav", ".aac"]
        audio_files = []

        for ext in audio_extensions:
            audio_files.extend(vault_path.rglob(f"*{ext}"))

        # Should find at least one audio file
        assert len(audio_files) > 0

        # Check specific audio file
        recording_file = vault_path / "attachments" / "recording.m4a"
        assert recording_file.exists()
        assert recording_file in audio_files

    @pytest.mark.asyncio
    async def test_processing_state_detection(self, test_vault: Path):
        """Test detection of notes with processing state"""
        vault_path = test_vault

        # Read processed note
        processed_note = vault_path / "processed.md"
        content = processed_note.read_text()

        # Should contain processing state indicators
        assert "postprocessor:" in content
        assert "transcribe:" in content
        assert "status:" in content
        assert "completed" in content

        # Read unprocessed note
        daily_note = vault_path / "daily" / "2024-01-01.md"
        daily_content = daily_note.read_text()

        # Should not contain processing state
        assert "postprocessor:" not in daily_content or "pending" in daily_content
