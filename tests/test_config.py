"""
Tests for configuration management.
"""

import os
import sys
import tempfile
from pathlib import Path

import pytest

# Add src to path first
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
# flake8: noqa: E402
from src.config import Config


class TestConfig:
    """Test configuration management."""

    def test_default_config(self):
        """Test default configuration values."""
        config = Config()

        assert config.vault_path == Path("./testvault/test-vault").resolve()
        assert (
            config.processor_script_path
            == Path("./processor/add_transcript_to_voicememo.py").resolve()
        )
        assert config.voice_patterns == ["*.webm", "*.mp3", "*.wav", "*.m4a"]
        assert config.state_method == "frontmatter"
        assert config.log_level == "INFO"
        assert config.watch_mode is False

    def test_env_var_override(self):
        """Test environment variable override."""
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_path = Path(temp_dir) / "vault"
            script_path = Path(temp_dir) / "script.py"

            # Create test files
            vault_path.mkdir()
            script_path.touch()

            # Set environment variables
            os.environ["VAULT_PATH"] = str(vault_path)
            os.environ["PROCESSOR_SCRIPT_PATH"] = str(script_path)
            os.environ["VOICE_PATTERNS"] = "*.wav,*.mp3"
            os.environ["STATE_METHOD"] = "vault_file"
            os.environ["LOG_LEVEL"] = "DEBUG"
            os.environ["WATCH_MODE"] = "true"

            try:
                config = Config()

                assert config.vault_path == vault_path.resolve()
                assert config.processor_script_path == script_path.resolve()
                assert config.voice_patterns == ["*.wav", "*.mp3"]
                assert config.state_method == "vault_file"
                assert config.log_level == "DEBUG"
                assert config.watch_mode is True
            finally:
                # Clean up environment variables
                for key in [
                    "VAULT_PATH",
                    "PROCESSOR_SCRIPT_PATH",
                    "VOICE_PATTERNS",
                    "STATE_METHOD",
                    "LOG_LEVEL",
                    "WATCH_MODE",
                ]:
                    if key in os.environ:
                        del os.environ[key]

    def test_invalid_state_method(self):
        """Test invalid state method raises error."""
        os.environ["STATE_METHOD"] = "invalid_method"

        try:
            with pytest.raises(ValueError, match="Invalid state method"):
                Config()
        finally:
            del os.environ["STATE_METHOD"]

    def test_invalid_log_level(self):
        """Test invalid log level raises error."""
        os.environ["LOG_LEVEL"] = "INVALID"

        try:
            with pytest.raises(ValueError, match="Invalid log level"):
                Config()
        finally:
            del os.environ["LOG_LEVEL"]

    def test_validation_missing_vault(self):
        """Test validation fails for missing vault."""
        with tempfile.TemporaryDirectory() as temp_dir:
            script_path = Path(temp_dir) / "script.py"
            script_path.touch()

            os.environ["VAULT_PATH"] = str(Path(temp_dir) / "nonexistent")
            os.environ["PROCESSOR_SCRIPT_PATH"] = str(script_path)

            try:
                config = Config()
                with pytest.raises(
                    ValueError, match="Vault path does not exist"
                ):
                    config.validate()
            finally:
                del os.environ["VAULT_PATH"]
                del os.environ["PROCESSOR_SCRIPT_PATH"]

    def test_validation_missing_script(self):
        """Test validation fails for missing script."""
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_path = Path(temp_dir) / "vault"
            vault_path.mkdir()

            os.environ["VAULT_PATH"] = str(vault_path)
            os.environ["PROCESSOR_SCRIPT_PATH"] = str(
                Path(temp_dir) / "nonexistent.py"
            )

            try:
                config = Config()
                with pytest.raises(
                    ValueError, match="Processor script does not exist"
                ):
                    config.validate()
            finally:
                del os.environ["VAULT_PATH"]
                del os.environ["PROCESSOR_SCRIPT_PATH"]

    def test_config_str_representation(self):
        """Test string representation of config."""
        config = Config()
        config_str = str(config)

        assert "Obsidian Post-Processor Configuration" in config_str
        assert "Vault Path:" in config_str
        assert "Processor Script:" in config_str
        assert "Voice Patterns:" in config_str
