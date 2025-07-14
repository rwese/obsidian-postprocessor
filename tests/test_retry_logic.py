"""
Tests for the retry logic in the ObsidianProcessor.

These tests verify that the processor handles failures gracefully by
testing only once per run (no instant retries) and provides proper
error handling for broken recordings.
"""

import logging
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from src.config import Config
from src.processor import ObsidianProcessor


class TestRetryLogic:
    """Test class for processor retry logic."""

    def create_test_vault_with_unprocessed(self, temp_dir):
        """Create a test vault with unprocessed recordings."""
        vault_path = Path(temp_dir) / "test_vault"
        vault_path.mkdir()

        # Create processor script
        processor_path = vault_path / "processor.py"
        processor_path.write_text(
            """#!/usr/bin/env python3
import sys
sys.exit(0)  # Success
"""
        )

        # Create test note with unprocessed recording
        note = vault_path / "Test Note.md"
        note.write_text(
            """---
title: Test Note
---

This note has an unprocessed recording.

![[Recording001.webm]]
"""
        )

        # Create the voice file
        voice_file = vault_path / "Recording001.webm"
        voice_file.write_text("fake audio data")

        return vault_path, processor_path

    def test_single_attempt_success(self, caplog):
        """Test single attempt processing when script execution succeeds."""
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_path, processor_path = self.create_test_vault_with_unprocessed(temp_dir)

            # Set up config using environment variables
            with patch.dict(
                os.environ,
                {
                    "VAULT_PATH": str(vault_path),
                    "PROCESSOR_SCRIPT_PATH": str(processor_path),
                    "VOICE_PATTERNS": "*.webm",
                },
            ):
                config = Config()

                # Create processor
                processor = ObsidianProcessor(config)

                # Mock the script runner to succeed on first attempt
                with patch.object(processor.script_runner, "run_script") as mock_run:
                    mock_run.return_value = True

                    # Connect processor
                    processor.connect()

                    # Clear logs
                    caplog.clear()
                    caplog.set_level(logging.INFO)

                    # Test single recording processing
                    result = processor._process_single_recording("Test Note", "Recording001.webm")

                    # Should succeed on first attempt
                    assert result is True

                    # Should have called run_script only once (no retries)
                    assert mock_run.call_count == 1

                    # Check log messages for processing (no retry attempts)
                    log_messages = [record.message for record in caplog.records]
                    assert any("Processing: Recording001.webm" in msg for msg in log_messages)
                    assert any(
                        "Successfully processed with enhanced tracking: Recording001.webm" in msg
                        for msg in log_messages
                    )

    def test_single_attempt_failure(self, caplog):
        """Test single attempt processing when script execution fails."""
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_path, processor_path = self.create_test_vault_with_unprocessed(temp_dir)

            # Set up config using environment variables
            with patch.dict(
                os.environ,
                {
                    "VAULT_PATH": str(vault_path),
                    "PROCESSOR_SCRIPT_PATH": str(processor_path),
                    "VOICE_PATTERNS": "*.webm",
                },
            ):
                config = Config()

                # Create processor
                processor = ObsidianProcessor(config)

                # Mock the script runner to always fail
                with patch.object(processor.script_runner, "run_script") as mock_run:
                    mock_run.return_value = False  # Always fail

                    # Connect processor
                    processor.connect()

                    # Clear logs
                    caplog.clear()
                    caplog.set_level(logging.INFO)

                    # Test single recording processing
                    result = processor._process_single_recording("Test Note", "Recording001.webm")

                    # Should fail on first attempt
                    assert result is False

                    # Should have called run_script only once (no retries)
                    assert mock_run.call_count == 1

                    # Check log messages for failure and broken marking
                    log_messages = [record.message for record in caplog.records]
                    assert any("Script execution failed for: Recording001.webm" in msg for msg in log_messages)
                    assert any("Marked Recording001.webm as failed" in msg for msg in log_messages)

    def test_exception_handling_single_attempt(self, caplog):
        """Test exception handling with single attempt."""
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_path, processor_path = self.create_test_vault_with_unprocessed(temp_dir)

            # Set up config using environment variables
            with patch.dict(
                os.environ,
                {
                    "VAULT_PATH": str(vault_path),
                    "PROCESSOR_SCRIPT_PATH": str(processor_path),
                    "VOICE_PATTERNS": "*.webm",
                },
            ):
                config = Config()

                # Create processor
                processor = ObsidianProcessor(config)

                # Mock the script runner to raise exception
                with patch.object(processor.script_runner, "run_script") as mock_run:
                    mock_run.side_effect = Exception("Network error")

                    # Connect processor
                    processor.connect()

                    # Clear logs
                    caplog.clear()
                    caplog.set_level(logging.INFO)

                    # Test single recording processing
                    result = processor._process_single_recording("Test Note", "Recording001.webm")

                    # Should fail due to exception
                    assert result is False

                    # Should have called run_script only once
                    assert mock_run.call_count == 1

                    # Check log messages for exception handling
                    log_messages = [record.message for record in caplog.records]
                    assert any("Error processing recording Recording001.webm" in msg for msg in log_messages)
                    assert any("Marked Recording001.webm as failed due to exception" in msg for msg in log_messages)

    def test_robust_batch_processing(self, caplog):
        """Test robust batch processing doesn't get stuck on errors."""
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_path, processor_path = self.create_test_vault_with_unprocessed(temp_dir)

            # Create additional test files
            note2 = vault_path / "Note2.md"
            note2.write_text(
                """---
title: Note 2
---

![[Recording002.webm]]
"""
            )

            note3 = vault_path / "Note3.md"
            note3.write_text(
                """---
title: Note 3
---

![[Recording003.webm]]
"""
            )

            # Create voice files
            (vault_path / "Recording002.webm").write_text("fake audio 2")
            (vault_path / "Recording003.webm").write_text("fake audio 3")

            # Set up config using environment variables
            with patch.dict(
                os.environ,
                {
                    "VAULT_PATH": str(vault_path),
                    "PROCESSOR_SCRIPT_PATH": str(processor_path),
                    "VOICE_PATTERNS": "*.webm",
                },
            ):
                config = Config()

                # Create processor
                processor = ObsidianProcessor(config)

                # Mock script runner: fail first recording, succeed others
                with patch.object(processor.script_runner, "run_script") as mock_run:
                    mock_run.side_effect = [
                        False,  # First recording fails
                        True,  # Second recording succeeds
                        True,  # Third recording succeeds
                    ]

                    # Connect processor
                    processor.connect()

                    # Clear logs
                    caplog.clear()
                    caplog.set_level(logging.INFO)

                    # Process entire vault
                    results = processor.process_vault(dry_run=False)

                    # Should have processed 2 successfully, 1 failed (single attempt each)
                    assert results["newly_processed"] == 2
                    assert results["failed_processing"] == 1

                    # Should have tried all recordings and not gotten stuck
                    log_messages = [record.message for record in caplog.records]
                    assert any("Processing completed: 2 successful, 1 failed" in msg for msg in log_messages)

    def test_state_management_error_no_retry(self, caplog):
        """Test that state management errors don't trigger retries."""
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_path, processor_path = self.create_test_vault_with_unprocessed(temp_dir)

            # Set up config using environment variables
            with patch.dict(
                os.environ,
                {
                    "VAULT_PATH": str(vault_path),
                    "PROCESSOR_SCRIPT_PATH": str(processor_path),
                    "VOICE_PATTERNS": "*.webm",
                },
            ):
                config = Config()

                # Create processor
                processor = ObsidianProcessor(config)

                # Mock script runner to succeed but state manager to fail
                with patch.object(processor.script_runner, "run_script") as mock_run:
                    mock_run.return_value = True

                    with patch.object(processor.state_manager, "mark_recording_processed") as mock_mark:
                        mock_mark.return_value = False  # State management fails

                        # Connect processor
                        processor.connect()

                        # Clear logs
                        caplog.clear()
                        caplog.set_level(logging.INFO)

                        # Test single recording processing
                        result = processor._process_single_recording("Test Note", "Recording001.webm")

                        # Should fail due to state management error
                        assert result is False

                        # Should have called run_script only once (no retries for state errors)
                        assert mock_run.call_count == 1

                        # Check log messages
                        log_messages = [record.message for record in caplog.records]
                        assert any("Failed to mark recording as processed" in msg for msg in log_messages)
