"""
Tests for frontmatter error handling.
"""

import logging
import sys
import tempfile
from pathlib import Path

# Add src to path first
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
# flake8: noqa: E402
from src.state_manager import StatelessStateManager


class TestFrontmatterErrorHandling:
    """Test frontmatter error handling."""

    def create_test_vault_with_malformed_frontmatter(self, temp_dir):
        """Create a test vault with malformed frontmatter."""
        vault_path = Path(temp_dir) / "vault"
        vault_path.mkdir()

        # Note with malformed YAML frontmatter
        note1 = vault_path / "Bad Frontmatter.md"
        note1.write_text(
            """---
title: Test Note
tags: [unclosed, array, missing bracket
processed_recordings: [bad, yaml, sequence
---

This note has malformed YAML frontmatter.

![[Recording001.webm]]
"""
        )

        # Note with good frontmatter
        note2 = vault_path / "Good Frontmatter.md"
        note2.write_text(
            """---
title: Good Note
processed_recordings:
  - Recording002.webm
---

This note has good frontmatter.

![[Recording003.webm]]
"""
        )

        return vault_path

    def test_silent_frontmatter_errors(self, caplog):
        """Test that SILENT level suppresses frontmatter errors."""
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_path = self.create_test_vault_with_malformed_frontmatter(
                temp_dir
            )

            # Set up state manager with SILENT error level
            manager = StatelessStateManager(vault_path, "SILENT")
            manager.connect()

            # Clear log
            caplog.clear()

            # This should not log any frontmatter errors
            processed = manager.get_processed_recordings("Bad Frontmatter")

            # Should return empty list for malformed frontmatter
            assert processed == []

            # Should not have any log messages
            assert len(caplog.records) == 0

    def test_debug_frontmatter_errors(self, caplog):
        """Test that DEBUG level shows frontmatter errors as debug."""
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_path = self.create_test_vault_with_malformed_frontmatter(
                temp_dir
            )

            # Set up state manager with DEBUG error level
            manager = StatelessStateManager(vault_path, "DEBUG")
            manager.connect()

            # Clear log and set level to DEBUG
            caplog.clear()
            caplog.set_level(logging.DEBUG)

            # This should log frontmatter errors as debug
            processed = manager.get_processed_recordings("Bad Frontmatter")

            # Should return empty list for malformed frontmatter
            assert processed == []

            # Should have debug log messages
            debug_messages = [
                record
                for record in caplog.records
                if record.levelname == "DEBUG"
            ]
            assert len(debug_messages) > 0
            assert any(
                "Frontmatter parsing error" in record.message
                for record in debug_messages
            )

    def test_warning_frontmatter_errors(self, caplog):
        """Test that WARNING level shows frontmatter errors as warnings."""
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_path = self.create_test_vault_with_malformed_frontmatter(
                temp_dir
            )

            # Set up state manager with WARNING error level (default)
            manager = StatelessStateManager(vault_path, "WARNING")
            manager.connect()

            # Clear log
            caplog.clear()

            # This should log frontmatter errors as warnings
            processed = manager.get_processed_recordings("Bad Frontmatter")

            # Should return empty list for malformed frontmatter
            assert processed == []

            # Should have warning log messages
            warning_messages = [
                record
                for record in caplog.records
                if record.levelname == "WARNING"
            ]
            assert len(warning_messages) > 0
            assert any(
                "Frontmatter parsing error" in record.message
                for record in warning_messages
            )

    def test_good_frontmatter_still_works(self):
        """Test that good frontmatter still works correctly."""
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_path = self.create_test_vault_with_malformed_frontmatter(
                temp_dir
            )

            # Set up state manager
            manager = StatelessStateManager(vault_path, "WARNING")
            manager.connect()

            # This should work fine
            processed = manager.get_processed_recordings("Good Frontmatter")

            # Should return the processed recording
            assert len(processed) == 1
            assert "Recording002.webm" in processed

    def test_parse_frontmatter_robustness(self):
        """Test that frontmatter parsing is robust."""
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_path = self.create_test_vault_with_malformed_frontmatter(
                temp_dir
            )

            manager = StatelessStateManager(vault_path, "SILENT")

            # Test various malformed frontmatter
            test_cases = [
                # Malformed YAML
                "---\ntitle: Test\ntags: [unclosed\n---\nContent",
                # No closing frontmatter
                "---\ntitle: Test\nContent without closing",
                # Empty frontmatter
                "---\n---\nContent",
                # Invalid YAML structure
                "---\ntitle: Test\n  - invalid\n    - nesting\n---\nContent",
                # No frontmatter
                "Just regular content",
            ]

            for i, content in enumerate(test_cases):
                frontmatter, body = manager._parse_frontmatter(content)

                # Should not crash and should return dict and string
                assert isinstance(frontmatter, dict)
                assert isinstance(body, str)
                assert "Content" in body or body == content
