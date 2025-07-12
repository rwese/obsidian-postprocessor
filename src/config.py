"""
Configuration management for Obsidian Post-Processor.

Environment variable based configuration for stateless operation.
"""

import os
from pathlib import Path
from typing import List, Optional


class Config:
    """Configuration class for Obsidian Post-Processor."""

    def __init__(self):
        self.vault_path = self._get_vault_path()
        self.processor_script_path = self._get_processor_script_path()
        self.voice_patterns = self._get_voice_patterns()
        self.state_method = self._get_state_method()
        self.log_level = self._get_log_level()
        self.watch_mode = self._get_watch_mode()
        self.frontmatter_error_level = self._get_frontmatter_error_level()

    def _get_vault_path(self) -> Path:
        """Get vault path from environment or default."""
        vault_path = os.getenv("VAULT_PATH", "./testvault/test-vault")
        return Path(vault_path).resolve()

    def _get_processor_script_path(self) -> Path:
        """Get processor script path from environment or default."""
        script_path = os.getenv(
            "PROCESSOR_SCRIPT_PATH", "./processor/add_transcript_to_voicememo.py"
        )
        return Path(script_path).resolve()

    def _get_voice_patterns(self) -> List[str]:
        """Get voice file patterns from environment or default."""
        patterns = os.getenv("VOICE_PATTERNS", "*.webm,*.mp3,*.wav,*.m4a")
        return [p.strip() for p in patterns.split(",")]

    def _get_state_method(self) -> str:
        """Get state tracking method from environment or default."""
        method = os.getenv("STATE_METHOD", "frontmatter")
        valid_methods = ["frontmatter", "vault_file", "inline"]
        if method not in valid_methods:
            raise ValueError(
                f"Invalid state method: {method}. Must be one of: {valid_methods}"
            )
        return method

    def _get_log_level(self) -> str:
        """Get log level from environment or default."""
        level = os.getenv("LOG_LEVEL", "INFO").upper()
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if level not in valid_levels:
            raise ValueError(
                f"Invalid log level: {level}. Must be one of: {valid_levels}"
            )
        return level

    def _get_watch_mode(self) -> bool:
        """Get watch mode from environment or default."""
        return os.getenv("WATCH_MODE", "false").lower() in ("true", "1", "yes", "on")

    def _get_frontmatter_error_level(self) -> str:
        """Get frontmatter error handling level from environment or default."""
        level = os.getenv("FRONTMATTER_ERROR_LEVEL", "WARNING").upper()
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL", "SILENT"]
        if level not in valid_levels:
            raise ValueError(
                f"Invalid frontmatter error level: {level}. Must be one of: {valid_levels}"
            )
        return level

    def validate(self) -> None:
        """Validate configuration."""
        if not self.vault_path.exists():
            raise ValueError(f"Vault path does not exist: {self.vault_path}")

        if not self.vault_path.is_dir():
            raise ValueError(f"Vault path is not a directory: {self.vault_path}")

        if not self.processor_script_path.exists():
            raise ValueError(
                f"Processor script does not exist: {self.processor_script_path}"
            )

        if not self.processor_script_path.is_file():
            raise ValueError(
                f"Processor script is not a file: {self.processor_script_path}"
            )

    def __str__(self) -> str:
        """String representation of configuration."""
        return f"""Obsidian Post-Processor Configuration:
  Vault Path: {self.vault_path}
  Processor Script: {self.processor_script_path}
  Voice Patterns: {self.voice_patterns}
  State Method: {self.state_method}
  Log Level: {self.log_level}
  Watch Mode: {self.watch_mode}
  Frontmatter Error Level: {self.frontmatter_error_level}"""
