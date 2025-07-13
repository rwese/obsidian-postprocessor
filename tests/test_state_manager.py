"""
Tests for state manager.
"""

import sys
import tempfile
from pathlib import Path

import pytest

# Add src to path first
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
# flake8: noqa: E402
from src.state_manager import StatelessStateManager


class TestStatelessStateManager:
    """Test stateless state management."""

    def create_test_vault(self, temp_dir):
        """Create a test vault with notes."""
        vault_path = Path(temp_dir) / "vault"
        vault_path.mkdir()

        # Note with existing frontmatter
        note1 = vault_path / "Processed Note.md"
        note1.write_text(
            """---
title: Processed Note
processed_recordings:
  - Recording001.webm
  - Recording002.mp3
---

This note has processed recordings.

![[Recording001.webm]]
![[Recording002.mp3]]
![[Recording003.wav]]
"""
        )

        # Note without frontmatter
        note2 = vault_path / "No Frontmatter.md"
        note2.write_text(
            """This note has no frontmatter.

![[Recording004.webm]]
"""
        )

        # Note with empty frontmatter
        note3 = vault_path / "Empty Frontmatter.md"
        note3.write_text(
            """---
---

This note has empty frontmatter.

![[Recording005.mp3]]
"""
        )

        return vault_path

    def test_get_processed_recordings(self):
        """Test getting processed recordings from frontmatter."""
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_path = self.create_test_vault(temp_dir)

            manager = StatelessStateManager(vault_path)
            manager.connect()

            # Note with processed recordings
            processed = manager.get_processed_recordings("Processed Note")
            assert len(processed) == 2
            assert "Recording001.webm" in processed
            assert "Recording002.mp3" in processed

            # Note without frontmatter
            processed = manager.get_processed_recordings("No Frontmatter")
            assert len(processed) == 0

            # Note with empty frontmatter
            processed = manager.get_processed_recordings("Empty Frontmatter")
            assert len(processed) == 0

    def test_get_unprocessed_recordings(self):
        """Test getting unprocessed recordings."""
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_path = self.create_test_vault(temp_dir)

            manager = StatelessStateManager(vault_path)
            manager.connect()

            # Note with some processed recordings
            all_recordings = [
                "Recording001.webm",
                "Recording002.mp3",
                "Recording003.wav",
            ]
            unprocessed = manager.get_unprocessed_recordings(
                "Processed Note", all_recordings
            )
            assert len(unprocessed) == 1
            assert "Recording003.wav" in unprocessed

            # Note with no processed recordings
            all_recordings = ["Recording004.webm"]
            unprocessed = manager.get_unprocessed_recordings(
                "No Frontmatter", all_recordings
            )
            assert len(unprocessed) == 1
            assert "Recording004.webm" in unprocessed

    def test_mark_recording_processed(self):
        """Test marking a recording as processed."""
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_path = self.create_test_vault(temp_dir)

            manager = StatelessStateManager(vault_path)
            manager.connect()

            # Mark recording as processed in note without frontmatter
            success = manager.mark_recording_processed(
                "No Frontmatter", "Recording004.webm"
            )
            assert success

            # Verify it was marked
            processed = manager.get_processed_recordings("No Frontmatter")
            assert "Recording004.webm" in processed

            # Mark another recording in same note
            success = manager.mark_recording_processed(
                "No Frontmatter", "Recording005.mp3"
            )
            assert success

            # Verify both are marked
            processed = manager.get_processed_recordings("No Frontmatter")
            assert len(processed) == 2
            assert "Recording004.webm" in processed
            assert "Recording005.mp3" in processed

            # Mark recording as processed in note with existing frontmatter
            success = manager.mark_recording_processed(
                "Processed Note", "Recording003.wav"
            )
            assert success

            # Verify it was added
            processed = manager.get_processed_recordings("Processed Note")
            assert len(processed) == 3
            assert "Recording003.wav" in processed

    def test_mark_recording_processed_duplicate(self):
        """Test marking same recording as processed multiple times."""
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_path = self.create_test_vault(temp_dir)

            manager = StatelessStateManager(vault_path)
            manager.connect()

            # Mark recording as processed
            success = manager.mark_recording_processed(
                "No Frontmatter", "Recording004.webm"
            )
            assert success

            # Mark same recording again
            success = manager.mark_recording_processed(
                "No Frontmatter", "Recording004.webm"
            )
            assert success

            # Should still only have one entry
            processed = manager.get_processed_recordings("No Frontmatter")
            assert len(processed) == 1
            assert processed.count("Recording004.webm") == 1

    def test_parse_frontmatter(self):
        """Test frontmatter parsing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_path = self.create_test_vault(temp_dir)

            manager = StatelessStateManager(vault_path)

            # Test with frontmatter
            content = """---
title: Test Note
tags:
  - test
processed_recordings:
  - Recording001.webm
---

This is the body content.
"""
            frontmatter, body = manager._parse_frontmatter(content)
            assert frontmatter["title"] == "Test Note"
            assert "test" in frontmatter["tags"]
            assert "Recording001.webm" in frontmatter["processed_recordings"]
            assert "This is the body content." in body

            # Test without frontmatter
            content = """This is just body content."""
            frontmatter, body = manager._parse_frontmatter(content)
            assert frontmatter == {}
            assert body == content

    def test_serialize_frontmatter(self):
        """Test frontmatter serialization."""
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_path = self.create_test_vault(temp_dir)

            manager = StatelessStateManager(vault_path)

            # Test with frontmatter
            frontmatter = {
                "title": "Test Note",
                "processed_recordings": ["Recording001.webm"],
            }
            body = "\nThis is the body content.\n"

            content = manager._serialize_frontmatter(frontmatter, body)
            assert content.startswith("---\n")
            assert "title: Test Note" in content
            assert "processed_recordings:" in content
            assert "Recording001.webm" in content
            assert "This is the body content." in content

            # Test without frontmatter
            content = manager._serialize_frontmatter({}, body)
            assert content == body

    def test_get_processing_stats(self):
        """Test getting processing statistics."""
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_path = self.create_test_vault(temp_dir)

            manager = StatelessStateManager(vault_path)
            manager.connect()

            # Mock notes with memos
            notes_with_memos = {
                "Processed Note": [
                    "Recording001.webm",
                    "Recording002.mp3",
                    "Recording003.wav",
                ],
                "No Frontmatter": ["Recording004.webm"],
            }

            stats = manager.get_processing_stats(notes_with_memos)

            assert stats["total_notes"] == 2
            assert stats["total_recordings"] == 4
            assert stats["processed_recordings"] == 2  # From 'Processed Note'
            assert (
                stats["unprocessed_recordings"] == 2
            )  # 1 from 'Processed Note' + 1 from 'No Frontmatter'

    def test_connection_required(self):
        """Test that connection is required before operations."""
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_path = Path(temp_dir) / "vault"
            vault_path.mkdir()

            manager = StatelessStateManager(vault_path)

            # Should raise error without connection
            with pytest.raises(RuntimeError, match="Vault not connected"):
                manager.get_processed_recordings("test")

    def test_mark_recording_processed_missing_note(self):
        """Test marking recording as processed for missing note."""
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_path = self.create_test_vault(temp_dir)

            manager = StatelessStateManager(vault_path)
            manager.connect()

            # Try to mark recording for non-existent note
            success = manager.mark_recording_processed(
                "NonExistent Note", "Recording.webm"
            )
            assert not success

    def test_find_note_file_in_subdirectories(self):
        """Test finding note files in subdirectories."""
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_path = Path(temp_dir) / "vault"
            vault_path.mkdir()

            # Create subdirectories with notes
            notes_dir = vault_path / "Notes"
            notes_dir.mkdir()
            daily_dir = vault_path / "Daily Notes"
            daily_dir.mkdir()

            # Create notes in different locations
            (vault_path / "Root Note.md").write_text("Root note content")
            (notes_dir / "Subdirectory Note.md").write_text("Subdirectory note content")
            (daily_dir / "Voice note test.md").write_text("Daily note content")

            manager = StatelessStateManager(vault_path)
            manager.connect()

            # Test finding note in vault root
            found_path = manager._find_note_file("Root Note")
            assert found_path == vault_path / "Root Note.md"

            # Test finding note in subdirectory
            found_path = manager._find_note_file("Subdirectory Note")
            assert found_path == notes_dir / "Subdirectory Note.md"

            # Test finding note with spaces in name (like the failing case)
            found_path = manager._find_note_file("Voice note test")
            assert found_path == daily_dir / "Voice note test.md"

            # Test non-existent note
            found_path = manager._find_note_file("NonExistent Note")
            assert found_path is None

    def test_mark_recording_processed_in_subdirectory(self):
        """Test marking recording as processed for note in subdirectory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_path = Path(temp_dir) / "vault"
            vault_path.mkdir()

            # Create note in subdirectory
            notes_dir = vault_path / "Notes"
            notes_dir.mkdir()
            note_file = notes_dir / "Voice note test.md"
            note_file.write_text(
                """---
title: Voice note test
---

This is a test note with voice recordings.

![[Recording 20250711132921.m4a]]
"""
            )

            manager = StatelessStateManager(vault_path)
            manager.connect()

            # Should successfully mark recording as processed
            success = manager.mark_recording_processed(
                "Voice note test", "Recording 20250711132921.m4a"
            )
            assert success

            # Verify it was marked
            processed = manager.get_processed_recordings("Voice note test")
            assert "Recording 20250711132921.m4a" in processed

    def test_find_note_file_edge_cases(self):
        """Test edge cases for note file finding."""
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_path = Path(temp_dir) / "vault"
            vault_path.mkdir()

            # Create note with .md already in the path
            (vault_path / "Test Note.md").write_text("Test content")

            manager = StatelessStateManager(vault_path)

            # Test with .md extension in input
            found_path = manager._find_note_file("Test Note.md")
            assert found_path == vault_path / "Test Note.md"

            # Test without .md extension
            found_path = manager._find_note_file("Test Note")
            assert found_path == vault_path / "Test Note.md"

    def test_broken_recordings_handling(self):
        """Test broken recordings management."""
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_path = self.create_test_vault(temp_dir)

            manager = StatelessStateManager(vault_path)
            manager.connect()

            # Initially no broken recordings
            broken = manager.get_broken_recordings("No Frontmatter")
            assert len(broken) == 0

            # Mark recording as broken
            success = manager.mark_recording_broken(
                "No Frontmatter", "broken.m4a", "File is corrupted"
            )
            assert success

            # Verify it was marked as broken
            broken = manager.get_broken_recordings("No Frontmatter")
            assert "broken.m4a" in broken
            assert len(broken) == 1

            # Test that broken recordings are excluded from unprocessed
            all_recordings = ["broken.m4a", "good.m4a"]
            unprocessed = manager.get_unprocessed_recordings(
                "No Frontmatter", all_recordings
            )
            assert "broken.m4a" not in unprocessed
            assert "good.m4a" in unprocessed
            assert len(unprocessed) == 1

    def test_mark_recording_broken_duplicate(self):
        """Test marking same recording as broken multiple times."""
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_path = self.create_test_vault(temp_dir)

            manager = StatelessStateManager(vault_path)
            manager.connect()

            # Mark recording as broken
            success = manager.mark_recording_broken(
                "No Frontmatter", "broken.m4a", "First error"
            )
            assert success

            # Mark same recording as broken again
            success = manager.mark_recording_broken(
                "No Frontmatter", "broken.m4a", "Second error"
            )
            assert success

            # Should still only have one entry
            broken = manager.get_broken_recordings("No Frontmatter")
            assert len(broken) == 1
            assert broken.count("broken.m4a") == 1

    def test_processing_stats_with_broken_recordings(self):
        """Test processing statistics include broken recordings."""
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_path = self.create_test_vault(temp_dir)

            manager = StatelessStateManager(vault_path)
            manager.connect()

            # Mark one recording as broken
            manager.mark_recording_broken(
                "Processed Note", "Recording003.wav", "Corrupted file"
            )

            # Mock notes with memos
            notes_with_memos = {
                "Processed Note": [
                    "Recording001.webm",
                    "Recording002.mp3",
                    "Recording003.wav",
                ],
                "No Frontmatter": ["Recording004.webm"],
            }

            stats = manager.get_processing_stats(notes_with_memos)

            assert stats["total_notes"] == 2
            assert stats["total_recordings"] == 4
            assert stats["processed_recordings"] == 2  # From 'Processed Note'
            assert stats["broken_recordings"] == 1  # Recording003.wav marked as broken
            assert (
                stats["unprocessed_recordings"] == 1
            )  # Only Recording004.webm from 'No Frontmatter'

    def test_broken_recordings_exclude_from_processing(self):
        """Test that broken recordings are excluded from unprocessed list."""
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_path = self.create_test_vault(temp_dir)

            manager = StatelessStateManager(vault_path)
            manager.connect()

            # Mark one recording as broken
            manager.mark_recording_broken(
                "Empty Frontmatter", "Recording005.mp3", "Corrupted"
            )

            # Test that it's excluded from unprocessed
            all_recordings = ["Recording005.mp3", "Recording006.wav"]
            unprocessed = manager.get_unprocessed_recordings(
                "Empty Frontmatter", all_recordings
            )

            assert "Recording005.mp3" not in unprocessed
            assert "Recording006.wav" in unprocessed
            assert len(unprocessed) == 1
