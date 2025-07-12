"""
Tests for template filtering functionality.
"""

import sys
import tempfile
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.voice_memo_detector import VoiceMemoDetector


class TestTemplateFiltering:
    """Test template filtering functionality."""

    def create_test_vault_with_templates(self, temp_dir):
        """Create a test vault with notes in templates directory."""
        vault_path = Path(temp_dir) / "vault"
        vault_path.mkdir()

        # Create templates directory (lowercase)
        templates_dir = vault_path / "templates"
        templates_dir.mkdir()

        # Create another directory for capitalized test
        other_dir = vault_path / "other"
        other_dir.mkdir()

        # Create Templates subdirectory for capitalized test
        templates_cap_dir = other_dir / "Templates"
        templates_cap_dir.mkdir(parents=True)

        # Create regular voice files
        voice_file1 = vault_path / "recording1.webm"
        voice_file1.write_text("fake audio 1")

        voice_file2 = vault_path / "recording2.webm"
        voice_file2.write_text("fake audio 2")

        # Create template voice files
        template_voice1 = templates_dir / "template_recording.webm"
        template_voice1.write_text("fake template audio 1")

        template_voice2 = templates_cap_dir / "template_recording2.webm"
        template_voice2.write_text("fake template audio 2")

        # Create regular note with voice file (should be processed)
        regular_note = vault_path / "Regular Note.md"
        regular_note.write_text(
            """---
title: Regular Note
---

This is a regular note with a voice memo.

![[recording1.webm]]
"""
        )

        # Create template note in templates/ directory (should be ignored)
        template_note1 = templates_dir / "Template Note.md"
        template_note1.write_text(
            """---
title: Template Note
---

This is a template note with a voice memo that should be ignored.

![[template_recording.webm]]
"""
        )

        # Create template note in other/Templates/ directory (should be ignored)
        template_note2 = templates_cap_dir / "Template Note 2.md"
        template_note2.write_text(
            """---
title: Template Note 2
---

This is another template note with a voice memo that should be ignored.

![[template_recording2.webm]]
"""
        )

        # Create another regular note (should be processed)
        regular_note2 = vault_path / "Another Regular Note.md"
        regular_note2.write_text(
            """---
title: Another Regular Note
---

This is another regular note with a voice memo.

![[recording2.webm]]
"""
        )

        return vault_path

    def test_templates_directory_ignored_lowercase(self):
        """Test that notes in lowercase 'templates/' directory are ignored."""
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_path = self.create_test_vault_with_templates(temp_dir)

            detector = VoiceMemoDetector(vault_path, ["*.webm"])
            detector.connect()

            # Get notes with voice memos
            notes_with_memos = detector.get_notes_with_voice_memos()

            # Should only find regular notes, not template notes
            assert len(notes_with_memos) == 2
            assert "Regular Note" in notes_with_memos
            assert "Another Regular Note" in notes_with_memos

            # Template notes should not be included
            assert "templates/Template Note" not in notes_with_memos
            assert "Templates/Template Note 2" not in notes_with_memos

    def test_templates_directory_ignored_capitalized(self):
        """Test that notes in capitalized 'Templates/' directory are ignored."""
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_path = self.create_test_vault_with_templates(temp_dir)

            detector = VoiceMemoDetector(vault_path, ["*.webm"])
            detector.connect()

            # Get notes with voice memos
            notes_with_memos = detector.get_notes_with_voice_memos()

            # Verify template notes are not in results
            note_paths = list(notes_with_memos.keys())
            template_notes = [
                path
                for path in note_paths
                if path.startswith("templates/") or path.startswith("Templates/")
            ]

            assert len(template_notes) == 0, f"Found template notes: {template_notes}"

    def test_should_ignore_note_method(self):
        """Test the _should_ignore_note method directly."""
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_path = Path(temp_dir) / "vault"
            vault_path.mkdir()

            # Create templates directory and notes for testing
            templates_dir = vault_path / "templates"
            templates_dir.mkdir()

            # Create a note in templates directory
            template_note = templates_dir / "My Template.md"
            template_note.write_text("Template content")

            # Create a regular note
            regular_note = vault_path / "Regular Note.md"
            regular_note.write_text("Regular content")

            # Create nested templates directory
            nested_dir = vault_path / "subfolder"
            nested_dir.mkdir()
            nested_templates_dir = nested_dir / "Templates"
            nested_templates_dir.mkdir()

            # Create note in nested templates directory
            nested_template_note = nested_templates_dir / "Nested Template.md"
            nested_template_note.write_text("Nested template content")

            detector = VoiceMemoDetector(vault_path, ["*.webm"])
            detector.connect()

            # Test cases - now using just note names as that's what obsidiantools provides
            assert detector._should_ignore_note("My Template") == True  # In templates/
            assert (
                detector._should_ignore_note("Nested Template") == True
            )  # In subfolder/Templates/

            # Regular notes should not be ignored
            assert detector._should_ignore_note("Regular Note") == False

    def test_vault_with_only_template_notes(self):
        """Test vault that only contains template notes."""
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_path = Path(temp_dir) / "vault"
            vault_path.mkdir()

            # Create only templates directory
            templates_dir = vault_path / "templates"
            templates_dir.mkdir()

            # Create template voice file
            template_voice = templates_dir / "template_recording.webm"
            template_voice.write_text("fake template audio")

            # Create only template note
            template_note = templates_dir / "Template Note.md"
            template_note.write_text(
                """---
title: Template Note
---

This is a template note with a voice memo that should be ignored.

![[template_recording.webm]]
"""
            )

            detector = VoiceMemoDetector(vault_path, ["*.webm"])
            detector.connect()

            # Get notes with voice memos
            notes_with_memos = detector.get_notes_with_voice_memos()

            # Should find no notes since all are templates
            assert len(notes_with_memos) == 0
