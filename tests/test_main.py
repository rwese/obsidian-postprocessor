"""
Test the main CLI interface
"""

from pathlib import Path

import pytest
from click.testing import CliRunner

from main import main


def test_main_help():
    """Test main CLI help output"""
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "Obsidian Post-Processor V2" in result.output


def test_main_validate_mode(config_file: Path):
    """Test validate mode"""
    runner = CliRunner()
    result = runner.invoke(main, ["--config", str(config_file), "--validate"])
    assert result.exit_code == 0
    assert "Configuration validation" in result.output


def test_main_dry_run_mode(config_file: Path, test_vault: Path):
    """Test dry run mode"""
    runner = CliRunner()
    result = runner.invoke(main, ["--config", str(config_file), "--vault-path", str(test_vault), "--dry-run"])
    assert result.exit_code == 0
    assert "Dry run mode:" in result.output
    assert "Scanning vault:" in result.output


def test_main_processing_mode(config_file: Path):
    """Test processing mode"""
    runner = CliRunner()
    result = runner.invoke(main, ["--config", str(config_file)])
    assert result.exit_code == 0
    assert "Processing mode:" in result.output
    assert "Core implementation needed:" in result.output


def test_main_log_level():
    """Test log level parameter"""
    runner = CliRunner()
    result = runner.invoke(main, ["--log-level", "DEBUG"])
    assert result.exit_code == 0


def test_main_invalid_log_level():
    """Test invalid log level parameter"""
    runner = CliRunner()
    result = runner.invoke(main, ["--log-level", "INVALID"])
    assert result.exit_code != 0


def test_main_missing_config():
    """Test missing config file"""
    runner = CliRunner()
    result = runner.invoke(main, ["--config", "nonexistent.yaml"])
    # Should succeed without --generate-config since config check is later
    assert result.exit_code == 0


def test_main_generate_config():
    """Test config generation"""
    runner = CliRunner()
    result = runner.invoke(main, ["--generate-config"])
    assert result.exit_code == 0
    assert "vault_path:" in result.output
    assert "exclude_patterns:" in result.output
    assert "processors:" in result.output
    assert "transcribe:" in result.output


def test_main_command_line_overrides(config_file: Path, test_vault: Path):
    """Test command-line configuration overrides"""
    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "--config",
            str(config_file),
            "--vault-path",
            str(test_vault),
            "--concurrency-limit",
            "10",
            "--timeout",
            "120",
            "--retry-attempts",
            "5",
            "--exclude-pattern",
            "custom/**",
            "--exclude-pattern",
            "temp/**",
            "--log-level",
            "DEBUG",
            "--dry-run",
        ],
    )
    assert result.exit_code == 0
    assert str(test_vault) in result.output
    assert "Concurrency limit: 10" in result.output
    assert "Timeout: 120s" in result.output
    assert "Retry attempts: 5" in result.output
    assert "Exclude patterns: 2 patterns" in result.output
    assert "Log level: DEBUG" in result.output


def test_main_validation_with_overrides(config_file: Path, test_vault: Path):
    """Test validation with command-line overrides"""
    runner = CliRunner()
    result = runner.invoke(main, ["--config", str(config_file), "--vault-path", str(test_vault), "--validate"])
    assert result.exit_code == 0
    assert "Configuration is valid" in result.output


def test_main_validation_missing_vault(temp_dir: Path):
    """Test validation with missing vault path"""
    # Create config without vault_path
    config_file = temp_dir / "no_vault_config.yaml"
    config_file.write_text(
        """
processing:
  concurrency_limit: 5
logging:
  level: INFO
"""
    )

    runner = CliRunner()
    result = runner.invoke(main, ["--config", str(config_file), "--validate"])
    assert result.exit_code == 0
    assert "vault_path is required" in result.output


def test_main_help_shows_new_options():
    """Test that help shows new command-line options"""
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "--vault-path" in result.output
    assert "--concurrency-limit" in result.output
    assert "--timeout" in result.output
    assert "--retry-attempts" in result.output
    assert "--exclude-pattern" in result.output
