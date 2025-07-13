"""
Tests for voice file path handling improvements.
"""

import sys
import tempfile
from pathlib import Path

# Add src to path first
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
# flake8: noqa: E402
from src.voice_memo_detector import VoiceMemoDetector


class TestPathHandling:
    """Test voice file path handling improvements."""

    def create_test_vault_with_voice_files(self, temp_dir):
        """Create a test vault with voice files in different locations."""
        vault_path = Path(temp_dir) / "vault"
        vault_path.mkdir()

        # Create voice files in different locations
        # 1. Voice file in vault root
        root_voice = vault_path / "root_recording.webm"
        root_voice.write_text("fake audio in root")

        # 2. Voice file in attachments folder
        attachments_dir = vault_path / "attachments"
        attachments_dir.mkdir()
        attachments_voice = attachments_dir / "attachments_recording.webm"
        attachments_voice.write_text("fake audio in attachments")

        # 3. Voice file in subdirectory
        subdir = vault_path / "subfolder"
        subdir.mkdir()
        subdir_voice = subdir / "subdir_recording.webm"
        subdir_voice.write_text("fake audio in subfolder")

        # Create notes referencing these voice files
        # Note in root referencing root voice file
        note1 = vault_path / "Root Note.md"
        note1.write_text(
            """---
title: Root Note
---

This note has a voice file in the root.

![[root_recording.webm]]
"""
        )

        # Note in root referencing attachments voice file
        note2 = vault_path / "Attachments Note.md"
        note2.write_text(
            """---
title: Attachments Note
---

This note has a voice file in attachments.

![[attachments_recording.webm]]
"""
        )

        # Note in subfolder referencing voice file in same subfolder
        note3 = subdir / "Subfolder Note.md"
        note3.write_text(
            """---
title: Subfolder Note
---

This note has a voice file in the same subfolder.

![[subdir_recording.webm]]
"""
        )

        return vault_path

    def test_voice_file_path_resolution_root(self):
        """Test that voice files in vault root are found correctly."""
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_path = self.create_test_vault_with_voice_files(temp_dir)

            detector = VoiceMemoDetector(vault_path, ["*.webm"])

            # Test root voice file resolution
            voice_path = detector.get_voice_file_path("Root Note", "root_recording.webm")
            expected_path = vault_path / "root_recording.webm"

            assert voice_path == expected_path
            assert voice_path.exists()

    def test_voice_file_path_resolution_attachments(self):
        """Test that voice files in attachments folder are found correctly."""
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_path = self.create_test_vault_with_voice_files(temp_dir)

            detector = VoiceMemoDetector(vault_path, ["*.webm"])

            # Test attachments voice file resolution
            voice_path = detector.get_voice_file_path("Attachments Note", "attachments_recording.webm")
            expected_path = vault_path / "attachments" / "attachments_recording.webm"

            assert voice_path == expected_path
            assert voice_path.exists()

    def test_voice_file_path_resolution_subdirectory(self):
        """Test that voice files in subdirectories are found correctly."""
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_path = self.create_test_vault_with_voice_files(temp_dir)

            detector = VoiceMemoDetector(vault_path, ["*.webm"])

            # Test subdirectory voice file resolution (obsidiantools returns just filename)
            voice_path = detector.get_voice_file_path("Subfolder Note", "subdir_recording.webm")
            expected_path = vault_path / "subfolder" / "subdir_recording.webm"

            assert voice_path == expected_path
            assert voice_path.exists()

    def test_voice_file_path_resolution_missing_file(self):
        """Test that missing voice files return expected path."""
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_path = self.create_test_vault_with_voice_files(temp_dir)

            detector = VoiceMemoDetector(vault_path, ["*.webm"])

            # Test missing voice file resolution
            voice_path = detector.get_voice_file_path("Root Note", "missing_recording.webm")
            expected_path = vault_path / "missing_recording.webm"

            assert voice_path == expected_path
            assert not voice_path.exists()

    def test_voice_file_verification_integration(self):
        """Test the complete voice file verification process."""
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_path = self.create_test_vault_with_voice_files(temp_dir)

            detector = VoiceMemoDetector(vault_path, ["*.webm"])
            detector.connect()

            # Get notes with voice memos
            notes_with_memos = detector.get_notes_with_voice_memos()

            # Should find 3 notes
            assert len(notes_with_memos) == 3

            # Verify all voice files are found
            verified_notes = detector.verify_voice_files_exist(notes_with_memos)

            # All notes should have verified voice files
            assert len(verified_notes) == 3

            # Check specific notes
            assert "Root Note" in verified_notes
            assert "Attachments Note" in verified_notes
            assert "Subfolder Note" in verified_notes  # obsidiantools returns just the filename

            # Check that each note has its expected voice file
            assert "root_recording.webm" in verified_notes["Root Note"]
            assert "attachments_recording.webm" in verified_notes["Attachments Note"]
            assert "subdir_recording.webm" in verified_notes["Subfolder Note"]
