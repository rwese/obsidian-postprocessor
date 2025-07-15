"""Configuration management for Obsidian Post-Processor V2."""

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)


@dataclass
class ProcessorConfig:
    """Configuration for a specific processor."""

    type: str
    config: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    timeout: int = 300
    retry_attempts: int = 3


@dataclass
class ProcessingConfig:
    """Processing behavior configuration."""

    concurrency_limit: int = 5
    retry_attempts: int = 3
    retry_delay: float = 1.0
    timeout: int = 300


@dataclass
class LoggingConfig:
    """Logging configuration."""

    level: str = "INFO"
    file: Optional[str] = None
    format: str = "structured"


@dataclass
class Config:
    """Main configuration for Obsidian Post-Processor V2."""

    vault_path: Path
    exclude_patterns: List[str] = field(default_factory=lambda: ["templates/**", ".obsidian/**", "**/.*"])
    processors: Dict[str, ProcessorConfig] = field(default_factory=dict)
    processing: ProcessingConfig = field(default_factory=ProcessingConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    dry_run: bool = False

    def __post_init__(self):
        """Validate configuration after initialization."""
        if not self.vault_path.exists():
            raise ValueError(f"Vault path does not exist: {self.vault_path}")

        if not self.vault_path.is_dir():
            raise ValueError(f"Vault path is not a directory: {self.vault_path}")


class ConfigLoader:
    """Handles loading and validation of configuration."""

    @staticmethod
    def find_config_file(config_path: Optional[Path] = None, vault_path: Optional[Path] = None) -> Optional[Path]:
        """Find configuration file in order of priority."""
        search_paths = []

        # 1. Explicit config path (highest priority)
        if config_path:
            search_paths.append(("explicit", config_path))

        # 2. Vault .obsidian directory (if vault_path provided)
        if vault_path:
            obsidian_config = vault_path / ".obsidian" / "obsidian-postprocessor.yaml"
            search_paths.append(("vault-specific", obsidian_config))

        # 3. Current directory (fallback)
        search_paths.append(("default", Path("config.yaml")))

        logger.debug("Configuration search order:")
        for source_type, path in search_paths:
            logger.debug(f"  {source_type}: {path}")

        # Return first existing config file
        for source_type, path in search_paths:
            if path.exists():
                logger.info(f"Using {source_type} configuration: {path}")
                return path
            else:
                logger.debug(f"Config not found: {path}")
                # If explicit config was requested but not found, return None immediately
                if source_type == "explicit":
                    logger.error(f"Explicit configuration file not found: {path}")
                    return None

        logger.warning("No configuration file found in any search location")
        return None

    @staticmethod
    def load_from_file(config_path: Path) -> Config:
        """Load configuration from YAML file."""
        try:
            with open(config_path, "r") as f:
                data = yaml.safe_load(f)

            return ConfigLoader._parse_config(data)

        except FileNotFoundError:
            logger.error(f"Configuration file not found: {config_path}")
            raise
        except yaml.YAMLError as e:
            logger.error(f"Invalid YAML in configuration file: {e}")
            raise
        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
            raise

    @staticmethod
    def load_with_search(config_path: Optional[Path] = None, vault_path: Optional[Path] = None) -> Optional[Config]:
        """Load configuration with automatic file discovery."""
        found_config = ConfigLoader.find_config_file(config_path, vault_path)

        if found_config:
            return ConfigLoader.load_from_file(found_config)

        logger.warning("No configuration file found in search paths")
        return None

    @staticmethod
    def _parse_config(data: Dict[str, Any]) -> Config:
        """Parse configuration data into Config object."""
        # Expand environment variables
        data = ConfigLoader._expand_env_vars(data)

        # Parse vault path
        vault_path = Path(data.get("vault_path", ".")).expanduser().resolve()

        # Parse exclude patterns
        exclude_patterns = data.get("exclude_patterns", [])

        # Parse processors
        processors = {}
        for name, proc_data in data.get("processors", {}).items():
            processors[name] = ProcessorConfig(
                type=proc_data.get("type", ""),
                config=proc_data.get("config", {}),
                enabled=proc_data.get("enabled", True),
                timeout=proc_data.get("timeout", 300),
                retry_attempts=proc_data.get("retry_attempts", 3),
            )

        # Parse processing config
        processing_data = data.get("processing", {})
        processing = ProcessingConfig(
            concurrency_limit=processing_data.get("concurrency_limit", 5),
            retry_attempts=processing_data.get("retry_attempts", 3),
            retry_delay=processing_data.get("retry_delay", 1.0),
            timeout=processing_data.get("timeout", 300),
        )

        # Parse logging config
        logging_data = data.get("logging", {})
        logging_config = LoggingConfig(
            level=logging_data.get("level", "INFO"),
            file=logging_data.get("file"),
            format=logging_data.get("format", "structured"),
        )

        # Parse dry run
        dry_run = data.get("dry_run", False)

        return Config(
            vault_path=vault_path,
            exclude_patterns=exclude_patterns,
            processors=processors,
            processing=processing,
            logging=logging_config,
            dry_run=dry_run,
        )

    @staticmethod
    def _expand_env_vars(data: Any) -> Any:
        """Recursively expand environment variables in configuration."""
        if isinstance(data, dict):
            return {k: ConfigLoader._expand_env_vars(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [ConfigLoader._expand_env_vars(item) for item in data]
        elif isinstance(data, str):
            # Expand ${VAR} and $VAR patterns
            import re

            pattern = r"\$\{([^}]+)\}|\$([A-Za-z_][A-Za-z0-9_]*)"

            def replacer(match):
                var_name = match.group(1) or match.group(2)
                return os.environ.get(var_name, match.group(0))

            return re.sub(pattern, replacer, data)
        else:
            return data

    @staticmethod
    def validate_config(config: Config) -> List[str]:
        """Validate configuration and return list of errors."""
        errors = []

        # Validate vault path
        if not config.vault_path.exists():
            errors.append(f"Vault path does not exist: {config.vault_path}")
        elif not config.vault_path.is_dir():
            errors.append(f"Vault path is not a directory: {config.vault_path}")

        # Validate processors
        for name, processor in config.processors.items():
            if not processor.type:
                errors.append(f"Processor '{name}' has no type specified")

            if processor.timeout <= 0:
                errors.append(f"Processor '{name}' timeout must be positive")

            if processor.retry_attempts < 0:
                errors.append(f"Processor '{name}' retry_attempts must be non-negative")

        # Validate processing config
        if config.processing.concurrency_limit <= 0:
            errors.append("Processing concurrency_limit must be positive")

        if config.processing.retry_delay < 0:
            errors.append("Processing retry_delay must be non-negative")

        if config.processing.timeout <= 0:
            errors.append("Processing timeout must be positive")

        # Validate logging config
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if config.logging.level.upper() not in valid_levels:
            errors.append(f"Invalid logging level: {config.logging.level}")

        return errors


def load_config(config_path: str = "config.yaml") -> Config:
    """Load configuration from file with validation."""
    config_path = Path(config_path)

    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    config = ConfigLoader.load_from_file(config_path)

    # Validate configuration
    errors = ConfigLoader.validate_config(config)
    if errors:
        error_msg = "Configuration validation failed:\n" + "\n".join(f"  - {error}" for error in errors)
        raise ValueError(error_msg)

    return config
