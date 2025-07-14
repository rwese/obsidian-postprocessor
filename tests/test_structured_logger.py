"""
Test suite for structured logging system.
"""

import json
import tempfile
import time
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from src.structured_logger import DetailedOutputWriter, StructuredFormatter, StructuredLogger


class TestStructuredLogger:
    """Test the StructuredLogger class."""

    def test_logger_initialization(self):
        """Test logger initialization with various configurations."""
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_path = Path(temp_dir)

            # Test normal mode
            logger = StructuredLogger("test", vault_path, "INFO", debug_mode=False)
            assert logger.name == "test"
            assert logger.vault_path == vault_path
            assert logger.debug_mode is False

            # Test debug mode
            debug_logger = StructuredLogger("debug_test", vault_path, "DEBUG", debug_mode=True)
            assert debug_logger.debug_mode is True
            assert debug_logger.logger.level == 10  # DEBUG level

    def test_operation_context_tracking(self):
        """Test operation context tracking and timing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_path = Path(temp_dir)
            logger = StructuredLogger("test", vault_path, "INFO")

            # Test operation start
            op_id = logger.log_operation_start("test_operation", param1="value1", param2="value2")
            assert op_id is not None
            assert len(logger.operation_stack) == 1

            # Test operation end
            logger.log_operation_end(op_id, success=True, result="success")
            assert len(logger.operation_stack) == 0
            assert logger.metrics["operations_completed"] == 1

    def test_operation_context_manager(self):
        """Test operation context manager."""
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_path = Path(temp_dir)
            logger = StructuredLogger("test", vault_path, "INFO")

            # Test successful operation
            with logger.operation_context("test_operation", param="value"):
                time.sleep(0.1)  # Simulate work

            assert logger.metrics["operations_completed"] == 1
            assert logger.metrics["operations_failed"] == 0
            assert logger.metrics["total_processing_time"] > 0

            # Test failed operation
            with pytest.raises(ValueError):
                with logger.operation_context("failing_operation"):
                    raise ValueError("Test error")

            assert logger.metrics["operations_completed"] == 1
            assert logger.metrics["operations_failed"] == 1

    def test_file_processing_logging(self):
        """Test file processing logging."""
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_path = Path(temp_dir)
            logger = StructuredLogger("test", vault_path, "INFO")

            # Test successful file processing
            logger.log_file_processing("test_note", "test_voice.m4a", "success", duration=1.5)
            assert logger.metrics["files_processed"] == 1

            # Test failed file processing
            logger.log_file_processing("test_note", "test_voice.m4a", "failed", error="Test error")
            assert logger.metrics["files_failed"] == 1

    def test_script_execution_logging(self):
        """Test script execution logging."""
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_path = Path(temp_dir)
            logger = StructuredLogger("test", vault_path, "INFO")

            # Test successful script execution
            logger.log_script_execution("script.py", ["arg1", "arg2"], True, 2.5, output="Success")
            assert logger.metrics["script_executions"] == 1

            # Test failed script execution
            logger.log_script_execution("script.py", ["arg1", "arg2"], False, 1.0, error="Script failed")
            assert logger.metrics["script_failures"] == 1

    def test_metrics_collection(self):
        """Test metrics collection."""
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_path = Path(temp_dir)
            logger = StructuredLogger("test", vault_path, "INFO")

            # Simulate various operations
            logger.log_operation_start("op1")
            logger.log_file_processing("note1", "voice1.m4a", "success")
            logger.log_script_execution("script.py", [], True, 1.0)

            metrics = logger.get_metrics()

            assert "operations_started" in metrics
            assert "files_processed" in metrics
            assert "script_executions" in metrics
            assert "timestamp" in metrics
            assert metrics["files_processed"] == 1
            assert metrics["script_executions"] == 1


class TestStructuredFormatter:
    """Test the StructuredFormatter class."""

    def test_regular_log_formatting(self):
        """Test formatting of regular log records."""
        formatter = StructuredFormatter(debug_mode=False)

        # Create a real log record
        import logging

        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        # Format should use standard format
        formatted = formatter.format(record)
        assert "Test message" in formatted
        assert "INFO" in formatted
        assert "test_logger" in formatted

    def test_structured_log_formatting_normal_mode(self):
        """Test formatting of structured log records in normal mode."""
        formatter = StructuredFormatter(debug_mode=False)

        # Create a real log record with structured data
        import logging

        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test structured message",
            args=(),
            exc_info=None,
        )

        # Add structured data
        record.structured = True
        record.event = "test_event"
        record.operation_id = "test_op_123"
        record.duration = 1.5

        formatted = formatter.format(record)
        assert "Test structured message" in formatted
        assert "INFO" in formatted

    def test_structured_log_formatting_debug_mode(self):
        """Test formatting of structured log records in debug mode."""
        formatter = StructuredFormatter(debug_mode=True)

        # Create a real log record with structured data
        import logging

        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test structured message",
            args=(),
            exc_info=None,
        )

        # Add structured data
        record.structured = True
        record.event = "test_event"
        record.operation_id = "test_op_123"
        record.duration = 1.5

        formatted = formatter.format(record)

        # In debug mode, should return JSON
        parsed = json.loads(formatted)
        assert parsed["event"] == "test_event"
        assert parsed["operation_id"] == "test_op_123"
        assert parsed["duration"] == 1.5
        assert parsed["level"] == "INFO"


class TestDetailedOutputWriter:
    """Test the DetailedOutputWriter class."""

    def test_initialization(self):
        """Test output writer initialization."""
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_path = Path(temp_dir)
            writer = DetailedOutputWriter(vault_path)

            assert writer.vault_path == vault_path
            assert writer.output_dir == vault_path / ".obsidian-postprocessor-logs"
            assert writer.output_dir.exists()

    def test_write_processing_details(self):
        """Test writing processing details."""
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_path = Path(temp_dir)
            writer = DetailedOutputWriter(vault_path)

            processing_details = {
                "start_time": time.time(),
                "duration": 1.5,
                "success": True,
                "script_output": "Processing completed successfully",
            }

            output_path = writer.write_processing_details("test_note", "test_voice.m4a", processing_details)

            assert output_path.exists()
            assert output_path.name == "test_note_test_voice_processing.json"

            # Read and verify content
            with open(output_path, "r") as f:
                data = json.load(f)

            assert data["note_path"] == "test_note"
            assert data["voice_file"] == "test_voice.m4a"
            assert data["processing_details"]["success"] is True
            assert data["processing_details"]["duration"] == 1.5

    def test_write_error_details(self):
        """Test writing error details."""
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_path = Path(temp_dir)
            writer = DetailedOutputWriter(vault_path)

            error_details = {
                "error": "Script execution failed",
                "error_type": "ScriptError",
                "duration": 0.5,
                "success": False,
            }

            error_path = writer.write_error_details("test_note", "test_voice.m4a", error_details)

            assert error_path.exists()
            assert error_path.name == "test_note_test_voice_error.json"

            # Read and verify content
            with open(error_path, "r") as f:
                data = json.load(f)

            assert data["note_path"] == "test_note"
            assert data["voice_file"] == "test_voice.m4a"
            assert data["error_details"]["success"] is False
            assert data["error_details"]["error"] == "Script execution failed"

    def test_cleanup_old_logs(self):
        """Test cleanup of old log files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_path = Path(temp_dir)
            writer = DetailedOutputWriter(vault_path)

            # Create some test log files
            old_file = writer.output_dir / "old_file.json"
            new_file = writer.output_dir / "new_file.json"

            old_file.write_text('{"test": "old"}')
            new_file.write_text('{"test": "new"}')

            # Modify old file timestamp to be older than 7 days
            old_time = time.time() - (8 * 24 * 60 * 60)  # 8 days ago
            import os

            os.utime(old_file, (old_time, old_time))

            # Run cleanup
            writer.cleanup_old_logs(max_age_days=7)

            # Check that only new file remains
            assert not old_file.exists()
            assert new_file.exists()


class TestIntegration:
    """Integration tests for the structured logging system."""

    def test_full_logging_workflow(self):
        """Test the complete logging workflow."""
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_path = Path(temp_dir)
            logger = StructuredLogger("integration_test", vault_path, "INFO", debug_mode=True)
            writer = DetailedOutputWriter(vault_path)

            # Simulate a complete processing workflow
            with logger.operation_context("process_voice_memo", note="test_note", voice="test.m4a"):
                # Simulate script execution
                logger.log_script_execution(
                    "transcribe.py", ["note.md", "voice.m4a"], True, 2.5, transcript="Hello world"
                )

                # Simulate file processing
                logger.log_file_processing("test_note", "test.m4a", "success", duration=3.0, transcript_length=11)

                # Write detailed output
                processing_details = {"success": True, "duration": 3.0, "transcript_length": 11, "model": "whisper-1"}
                writer.write_processing_details("test_note", "test.m4a", processing_details)

            # Verify metrics
            metrics = logger.get_metrics()
            assert metrics["operations_completed"] == 1
            assert metrics["files_processed"] == 1
            assert metrics["script_executions"] == 1

            # Verify output file was created
            output_files = list(writer.output_dir.glob("*.json"))
            assert len(output_files) == 1
            assert "test_note_test_processing.json" in output_files[0].name

    @patch("src.structured_logger.logging.getLogger")
    def test_logger_with_mocked_handler(self, mock_get_logger):
        """Test logger with mocked handler to verify log calls."""
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger

        with tempfile.TemporaryDirectory() as temp_dir:
            vault_path = Path(temp_dir)
            logger = StructuredLogger("mock_test", vault_path, "INFO")

            # Test that logger methods call the underlying logger
            logger.info("Test message", extra_data="test")
            logger.error("Error message", error_code=500)

            # Verify calls were made (exact verification depends on mock setup)
            assert mock_logger.info.called or mock_logger.log.called
            assert mock_logger.error.called or mock_logger.log.called
