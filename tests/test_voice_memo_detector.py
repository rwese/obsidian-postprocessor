"""
Tests for voice memo detector.
"""

import sys
import tempfile
from pathlib import Path

import pytest

# Add src to path first
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
# flake8: noqa: E402
from src.voice_memo_detector import VoiceMemoDetector


class TestVoiceMemoDetector:
    """Test voice memo detection."""

    def create_test_vault(self, temp_dir):
        """Create a test vault with voice memos."""
        vault_path = Path(temp_dir) / "vault"
        vault_path.mkdir()

        # Create test notes
        note1 = vault_path / "Voice Memo 1.md"
        note1.write_text(
            """---
title: Voice Memo 1
---

Here is a voice memo:

![[Recording001.webm]]

And another one:

![[Recording002.mp3]]
"""
        )

        note2 = vault_path / "Voice Memo 2.md"
        note2.write_text(
            """---
title: Voice Memo 2
---

No voice memos here, just text.
"""
        )

        note3 = vault_path / "Mixed Content.md"
        note3.write_text(
            """---
title: Mixed Content
---

Some text and a voice memo:

![[Audio_Note.wav]]

And an image:

![[image.png]]
"""
        )

        # Create voice files
        (vault_path / "Recording001.webm").touch()
        (vault_path / "Recording002.mp3").touch()
        (vault_path / "Audio_Note.wav").touch()

        return vault_path

    def test_voice_patterns(self):
        """Test voice pattern building."""
        patterns = ["*.webm", "*.mp3", "*.wav"]
        detector = VoiceMemoDetector(Path("/tmp"), patterns)

        pattern = detector._build_extension_pattern()
        assert "webm" in pattern
        assert "mp3" in pattern
        assert "wav" in pattern
        assert "|" in pattern

    def test_extract_voice_files_from_note(self):
        """Test extraction of voice files from note content."""
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_path = self.create_test_vault(temp_dir)

            patterns = ["*.webm", "*.mp3", "*.wav", "*.m4a"]
            detector = VoiceMemoDetector(vault_path, patterns)
            detector.connect()

            # Test note with multiple voice files
            voice_files = detector._extract_voice_files_from_note("Voice Memo 1")
            assert len(voice_files) == 2
            assert "Recording001.webm" in voice_files
            assert "Recording002.mp3" in voice_files

            # Test note with no voice files
            voice_files = detector._extract_voice_files_from_note("Voice Memo 2")
            assert len(voice_files) == 0

            # Test note with one voice file
            voice_files = detector._extract_voice_files_from_note("Mixed Content")
            assert len(voice_files) == 1
            assert "Audio_Note.wav" in voice_files

    def test_get_notes_with_voice_memos(self):
        """Test getting all notes with voice memos."""
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_path = self.create_test_vault(temp_dir)

            patterns = ["*.webm", "*.mp3", "*.wav", "*.m4a"]
            detector = VoiceMemoDetector(vault_path, patterns)
            detector.connect()

            notes_with_memos = detector.get_notes_with_voice_memos()

            # Should find 2 notes with voice memos
            assert len(notes_with_memos) == 2
            assert "Voice Memo 1" in notes_with_memos
            assert "Mixed Content" in notes_with_memos
            assert "Voice Memo 2" not in notes_with_memos

            # Check voice files
            assert len(notes_with_memos["Voice Memo 1"]) == 2
            assert len(notes_with_memos["Mixed Content"]) == 1

    def test_get_voice_file_path(self):
        """Test getting voice file path."""
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_path = self.create_test_vault(temp_dir)

            patterns = ["*.webm", "*.mp3", "*.wav", "*.m4a"]
            detector = VoiceMemoDetector(vault_path, patterns)
            detector.connect()

            # Test existing file
            voice_path = detector.get_voice_file_path("Voice Memo 1", "Recording001.webm")
            assert voice_path.exists()
            assert voice_path.name == "Recording001.webm"

            # Test non-existing file
            voice_path = detector.get_voice_file_path("Voice Memo 1", "NonExistent.webm")
            assert not voice_path.exists()
            assert voice_path.name == "NonExistent.webm"

    def test_verify_voice_files_exist(self):
        """Test verification of voice files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_path = self.create_test_vault(temp_dir)

            patterns = ["*.webm", "*.mp3", "*.wav", "*.m4a"]
            detector = VoiceMemoDetector(vault_path, patterns)
            detector.connect()

            # Get all notes with voice memos
            notes_with_memos = detector.get_notes_with_voice_memos()

            # Verify files exist
            verified_notes = detector.verify_voice_files_exist(notes_with_memos)

            # All files should exist
            assert len(verified_notes) == 2
            assert "Voice Memo 1" in verified_notes
            assert "Mixed Content" in verified_notes

            # Remove one file and test again
            (vault_path / "Recording001.webm").unlink()
            verified_notes = detector.verify_voice_files_exist(notes_with_memos)

            # Should still have Mixed Content, but Voice Memo 1 should have fewer files
            assert len(verified_notes) == 2
            assert len(verified_notes["Voice Memo 1"]) == 1  # Only Recording002.mp3 remains
            assert len(verified_notes["Mixed Content"]) == 1

    def test_connection_required(self):
        """Test that connection is required before operations."""
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_path = Path(temp_dir) / "vault"
            vault_path.mkdir()

            patterns = ["*.webm", "*.mp3", "*.wav", "*.m4a"]
            detector = VoiceMemoDetector(vault_path, patterns)

            # Should raise error without connection
            with pytest.raises(RuntimeError, match="Vault not connected"):
                detector.get_notes_with_voice_memos()
