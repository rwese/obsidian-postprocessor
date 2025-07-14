"""
Enhanced structured logging system for Obsidian Post-Processor.

Provides structured logging with timing, context, and detailed output files.
"""

import json
import logging
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


class StructuredLogger:
    """Enhanced logger with structured output and timing capabilities."""

    def __init__(self, name: str, vault_path: Path, log_level: str = "INFO", debug_mode: bool = False):
        self.name = name
        self.vault_path = vault_path
        self.debug_mode = debug_mode
        self.logger = logging.getLogger(name)
        self.operation_stack = []
        self.metrics = {
            "operations_started": 0,
            "operations_completed": 0,
            "operations_failed": 0,
            "total_processing_time": 0,
            "files_processed": 0,
            "files_failed": 0,
            "script_executions": 0,
            "script_failures": 0,
            "avg_processing_time": 0,
        }

        # Setup enhanced logging format
        self._setup_logging(log_level)

    def _setup_logging(self, log_level: str):
        """Setup enhanced logging with structured format."""
        handler = logging.StreamHandler()
        formatter = StructuredFormatter(debug_mode=self.debug_mode)
        handler.setFormatter(formatter)

        self.logger.handlers.clear()
        self.logger.addHandler(handler)
        self.logger.setLevel(getattr(logging, log_level.upper()))
        self.logger.propagate = False

    def log_operation_start(self, operation: str, **context):
        """Log the start of an operation with context."""
        start_time = time.time()
        operation_id = f"{operation}_{int(start_time * 1000)}"

        operation_context = {
            "operation_id": operation_id,
            "operation": operation,
            "start_time": start_time,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "context": context,
        }

        self.operation_stack.append(operation_context)
        self.metrics["operations_started"] += 1

        self.logger.info(
            f"Starting operation: {operation}",
            extra={
                "structured": True,
                "operation_id": operation_id,
                "operation": operation,
                "event": "operation_start",
                "context": context,
            },
        )

        return operation_id

    def log_operation_end(self, operation_id: str, success: bool = True, **result_data):
        """Log the end of an operation with timing and results."""
        end_time = time.time()

        # Find the operation in the stack
        operation_context = None
        for i, op in enumerate(self.operation_stack):
            if op["operation_id"] == operation_id:
                operation_context = self.operation_stack.pop(i)
                break

        if not operation_context:
            self.logger.warning(f"Operation {operation_id} not found in stack")
            return

        duration = end_time - operation_context["start_time"]

        if success:
            self.metrics["operations_completed"] += 1
        else:
            self.metrics["operations_failed"] += 1

        self.metrics["total_processing_time"] += duration

        # Calculate average processing time
        total_ops = self.metrics["operations_completed"] + self.metrics["operations_failed"]
        if total_ops > 0:
            self.metrics["avg_processing_time"] = self.metrics["total_processing_time"] / total_ops

        log_level = logging.INFO if success else logging.ERROR
        status = "completed" if success else "failed"

        self.logger.log(
            log_level,
            f"Operation {status}: {operation_context['operation']} ({duration:.2f}s)",
            extra={
                "structured": True,
                "operation_id": operation_id,
                "operation": operation_context["operation"],
                "event": "operation_end",
                "success": success,
                "duration": duration,
                "result_data": result_data,
                "context": operation_context["context"],
            },
        )

    @contextmanager
    def operation_context(self, operation: str, **context):
        """Context manager for operations with automatic timing."""
        operation_id = self.log_operation_start(operation, **context)
        try:
            yield operation_id
            self.log_operation_end(operation_id, success=True)
        except Exception as e:
            self.log_operation_end(operation_id, success=False, error=str(e))
            raise

    def log_file_processing(self, note_path: str, voice_file: str, status: str, **metadata):
        """Log file processing with detailed metadata."""
        if status == "success":
            self.metrics["files_processed"] += 1
        elif status == "failed":
            self.metrics["files_failed"] += 1

        log_level = logging.INFO if status == "success" else logging.ERROR

        self.logger.log(
            log_level,
            f"File processing {status}: {voice_file} in {note_path}",
            extra={
                "structured": True,
                "event": "file_processing",
                "note_path": note_path,
                "voice_file": voice_file,
                "status": status,
                "metadata": metadata,
            },
        )

    def log_script_execution(
        self, script_path: str, script_args: List[str], success: bool, duration: float, **result_data
    ):
        """Log script execution with detailed results."""
        if success:
            self.metrics["script_executions"] += 1
        else:
            self.metrics["script_failures"] += 1

        log_level = logging.INFO if success else logging.ERROR
        status = "success" if success else "failed"

        self.logger.log(
            log_level,
            f"Script execution {status}: {script_path} ({duration:.2f}s)",
            extra={
                "structured": True,
                "event": "script_execution",
                "script_path": script_path,
                "script_args": script_args,
                "success": success,
                "duration": duration,
                "result_data": result_data,
            },
        )

    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics for monitoring."""
        return {
            **self.metrics,
            "active_operations": len(self.operation_stack),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def debug(self, message: str, **kwargs):
        """Debug logging with structured data."""
        self.logger.debug(message, extra={"structured": True, "event": "debug", **kwargs})

    def info(self, message: str, **kwargs):
        """Info logging with structured data."""
        self.logger.info(message, extra={"structured": True, "event": "info", **kwargs})

    def warning(self, message: str, **kwargs):
        """Warning logging with structured data."""
        self.logger.warning(message, extra={"structured": True, "event": "warning", **kwargs})

    def error(self, message: str, **kwargs):
        """Error logging with structured data."""
        self.logger.error(message, extra={"structured": True, "event": "error", **kwargs})


class StructuredFormatter(logging.Formatter):
    """Custom formatter for structured logging."""

    def __init__(self, debug_mode: bool = False):
        self.debug_mode = debug_mode
        super().__init__()

    def format(self, record):
        # Base format for regular logs
        base_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

        # Check if this is a structured log
        if hasattr(record, "structured") and record.structured:
            return self._format_structured(record)
        else:
            # Use standard format for non-structured logs
            formatter = logging.Formatter(base_format)
            return formatter.format(record)

    def _format_structured(self, record):
        """Format structured log records."""
        timestamp = datetime.now(timezone.utc).isoformat()

        # Base structured data
        structured_data = {
            "timestamp": timestamp,
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "event": getattr(record, "event", "general"),
        }

        # Add all extra fields from the record
        for key, value in record.__dict__.items():
            if key not in [
                "name",
                "msg",
                "args",
                "levelname",
                "levelno",
                "pathname",
                "filename",
                "module",
                "lineno",
                "funcName",
                "created",
                "msecs",
                "relativeCreated",
                "thread",
                "threadName",
                "processName",
                "process",
                "message",
                "exc_info",
                "exc_text",
                "stack_info",
                "structured",
            ]:
                structured_data[key] = value

        if self.debug_mode:
            # In debug mode, output JSON for better parsing
            return json.dumps(structured_data, indent=2, default=str)
        else:
            # In normal mode, use human-readable format
            return f"{timestamp} - {record.name} - {record.levelname} - {record.getMessage()}"


class DetailedOutputWriter:
    """Writes detailed processing output files next to notes."""

    def __init__(self, vault_path: Path):
        self.vault_path = vault_path
        self.output_dir = vault_path / ".obsidian-postprocessor-logs"
        self.output_dir.mkdir(exist_ok=True)

    def write_processing_details(self, note_path: str, voice_file: str, processing_details: Dict[str, Any]):
        """Write detailed processing information to a file next to the note."""
        # Create output filename
        note_name = Path(note_path).stem
        voice_name = Path(voice_file).stem
        output_filename = f"{note_name}_{voice_name}_processing.json"
        output_path = self.output_dir / output_filename

        # Prepare detailed output
        detailed_output = {
            "note_path": note_path,
            "voice_file": voice_file,
            "processing_timestamp": datetime.now(timezone.utc).isoformat(),
            "processing_details": processing_details,
        }

        # Write to file
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(detailed_output, f, indent=2, default=str)

        return output_path

    def write_error_details(self, note_path: str, voice_file: str, error_details: Dict[str, Any]):
        """Write detailed error information to a file."""
        # Create error output filename
        note_name = Path(note_path).stem
        voice_name = Path(voice_file).stem
        error_filename = f"{note_name}_{voice_name}_error.json"
        error_path = self.output_dir / error_filename

        # Prepare error output
        error_output = {
            "note_path": note_path,
            "voice_file": voice_file,
            "error_timestamp": datetime.now(timezone.utc).isoformat(),
            "error_details": error_details,
        }

        # Write to file
        with open(error_path, "w", encoding="utf-8") as f:
            json.dump(error_output, f, indent=2, default=str)

        return error_path

    def cleanup_old_logs(self, max_age_days: int = 7):
        """Clean up old log files."""
        if not self.output_dir.exists():
            return

        cutoff_time = time.time() - (max_age_days * 24 * 60 * 60)

        for log_file in self.output_dir.glob("*.json"):
            if log_file.stat().st_mtime < cutoff_time:
                log_file.unlink()

