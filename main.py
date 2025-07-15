#!/usr/bin/env python3
"""
Obsidian Post-Processor V2 - Minimal async voice memo processor
"""

import asyncio
import fnmatch
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import click
import yaml

from obsidian_processor.parser import FrontmatterParser
from obsidian_processor.processors import create_processor_registry_from_config
from obsidian_processor.scanner import VaultScanner
from obsidian_processor.state import StateManager


@click.command()
@click.option(
    "--config",
    default="config.yaml",
    help="Path to configuration file",
    type=click.Path(path_type=Path),
)
@click.option("--dry-run", is_flag=True, help="Show what would be processed without executing")
@click.option("--validate", is_flag=True, help="Validate configuration and exit")
@click.option("--generate-config", is_flag=True, help="Generate default configuration to stdout")
@click.option(
    "--log-level",
    default="INFO",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"], case_sensitive=False),
    help="Set logging level",
)
@click.option(
    "--vault-path",
    help="Path to Obsidian vault (overrides config file)",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
)
@click.option(
    "--concurrency-limit",
    help="Maximum concurrent processing tasks",
    type=int,
)
@click.option(
    "--timeout",
    help="Processing timeout in seconds",
    type=int,
)
@click.option(
    "--retry-attempts",
    help="Number of retry attempts for failed processing",
    type=int,
)
@click.option(
    "--exclude-pattern",
    help="Exclusion pattern (can be used multiple times)",
    multiple=True,
)
def main(
    config: Path,
    dry_run: bool,
    validate: bool,
    generate_config: bool,
    log_level: str,
    vault_path: Path,
    concurrency_limit: int,
    timeout: int,
    retry_attempts: int,
    exclude_pattern: tuple,
):
    """
    Obsidian Post-Processor V2 - Process voice memos in Obsidian vaults
    """
    if generate_config:
        print(
            """# Obsidian Post-Processor V2 Configuration
# Save this to config.yaml and customize for your vault

vault_path: "/path/to/your/obsidian/vault"

# Exclusion patterns (glob syntax)
exclude_patterns:
  - "templates/**"
  - "archive/**"
  - "**/*.template.md"
  - "**/.*"  # Hidden files

# Processing configuration
processing:
  concurrency_limit: 5
  retry_attempts: 3
  retry_delay: 1.0
  timeout: 300

# Processor definitions
processors:
  transcribe:
    type: "whisper"
    config:
      api_key: "${OPENAI_API_KEY}"
      model: "whisper-1"
      language: "auto"

  # Example custom script processor
  # custom_script:
  #   type: "script"
  #   config:
  #     command: "python scripts/custom.py {audio_file} {note_file}"
  #     timeout: 120

# Logging configuration
logging:
  level: "INFO"
  file: "logs/processor.log"
  format: "structured"
"""
        )
        return

    # Build effective configuration from file + CLI overrides
    effective_config = {}

    # Load config file if it exists
    if config.exists():
        try:
            with open(config) as f:
                config_content = f.read()
                # Interpolate environment variables
                config_content = interpolate_env_vars(config_content)
                effective_config = yaml.safe_load(config_content) or {}
        except Exception as e:
            print(f"Error loading config file: {e}")
            return

    # Apply command-line overrides
    if vault_path:
        effective_config["vault_path"] = str(vault_path)

    if concurrency_limit is not None:
        effective_config.setdefault("processing", {})["concurrency_limit"] = concurrency_limit

    if timeout is not None:
        effective_config.setdefault("processing", {})["timeout"] = timeout

    if retry_attempts is not None:
        effective_config.setdefault("processing", {})["retry_attempts"] = retry_attempts

    if exclude_pattern:
        effective_config["exclude_patterns"] = list(exclude_pattern)

    # Always set log level from CLI
    effective_config.setdefault("logging", {})["level"] = log_level

    # Validate configuration values
    validation_errors = validate_config_values(effective_config)
    if validation_errors:
        print("ERROR: Configuration validation errors:")
        for error in validation_errors:
            print(f"   - {error}")
        return

    print("Obsidian Post-Processor V2 - Configuration loaded")
    print(f"Config file: {config}")
    print(f"Vault path: {effective_config.get('vault_path', 'NOT SET')}")
    print(f"Log level: {effective_config.get('logging', {}).get('level', 'INFO')}")

    if effective_config.get("processing"):
        processing = effective_config["processing"]
        print(f"Concurrency limit: {processing.get('concurrency_limit', 5)}")
        print(f"Timeout: {processing.get('timeout', 300)}s")
        print(f"Retry attempts: {processing.get('retry_attempts', 3)}")

    if effective_config.get("exclude_patterns"):
        patterns = effective_config["exclude_patterns"]
        if isinstance(patterns, list):
            print(f"Exclude patterns: {len(patterns)} patterns")
        else:
            print("Exclude patterns: 1 pattern (converted from string)")
            effective_config["exclude_patterns"] = [str(patterns)]

    if validate:
        print("\nConfiguration validation:")

        # Validate vault path
        vault_validation = validate_vault_path(effective_config)
        if vault_validation:
            print(f"ERROR: ERROR: {vault_validation}")
            return

        # Validate processors
        processor_validation = validate_processors(effective_config)
        if processor_validation:
            print("ERROR: ERROR: Processor validation failed:")
            for error in processor_validation:
                print(f"   - {error}")
            return

        print("SUCCESS: Configuration is valid")
        return

    if dry_run:
        vault_validation = validate_vault_path(effective_config)
        if vault_validation:
            print(f"ERROR: ERROR: {vault_validation}")
            return

        print("\nDry run mode:")
        print("SUCCESS: Configuration loaded and validated")

        # Actually scan the vault
        vault_path_obj = Path(effective_config["vault_path"])
        exclude_patterns = effective_config.get("exclude_patterns", [])

        print(f"\n Scanning vault: {vault_path_obj}")
        if exclude_patterns:
            print(f" Exclusion patterns: {len(exclude_patterns)} patterns")
            for pattern in exclude_patterns:
                print(f"   - {pattern}")

        # Scan for markdown files
        markdown_files = scan_vault_for_markdown(vault_path_obj, exclude_patterns)
        print(f"\n Found {len(markdown_files)} markdown files")

        # Parse files for voice attachments
        files_with_audio = scan_for_voice_attachments(markdown_files, vault_path_obj)

        if files_with_audio:
            print(f"\n  Found {len(files_with_audio)} files with voice attachments:")
            for file_info in files_with_audio:
                print(f"    {file_info['note_path']}")
                for audio in file_info["audio_files"]:
                    print(f"       {audio['file']} ({audio['type']})")

                    # Show what would be processed
                    processors = effective_config.get("processors", {})
                    for proc_name, proc_config in processors.items():
                        state = file_info.get("state", {}).get(proc_name, "pending")
                        print(f"         → {proc_name}: {state}")
        else:
            print("\nSUCCESS: No voice attachments found to process")

        return

    print("\nProcessing mode:")
    print("SUCCESS: Configuration loaded and validated")

    # Run the actual processing
    asyncio.run(run_processing(effective_config, dry_run))


async def run_processing(config: Dict[str, Any], dry_run: bool = False):
    """Run the actual processing using the new implementation."""
    import logging

    # Set up logging
    log_level = config.get("logging", {}).get("level", "INFO")
    logging.basicConfig(
        level=getattr(logging, log_level.upper()), format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    logger = logging.getLogger(__name__)

    try:
        # Load configuration using new system
        vault_path = Path(config["vault_path"])
        exclude_patterns = config.get("exclude_patterns", [])
        processors_config = config.get("processors", {})

        # Initialize components
        scanner = VaultScanner(vault_path, exclude_patterns)
        parser = FrontmatterParser()
        state_manager = StateManager(dry_run=dry_run)

        # Create processor registry
        processor_registry = create_processor_registry_from_config(processors_config)

        print(" Scanning vault for voice memos...")

        # Scan vault
        notes_processed = 0
        notes_with_audio = 0
        processing_results = []

        async for note_info in scanner.scan_vault():
            notes_processed += 1
            notes_with_audio += 1

            # Parse the note
            try:
                parsed_note = await parser.parse_note(note_info.note_path)

                print(f" Processing: {note_info.note_path.name}")
                print(f"    Audio files: {len(note_info.attachments)}")

                # Process with each configured processor
                for processor_name in processor_registry.list_processors():
                    # Check if we should process this note
                    if await state_manager.should_process(note_info.note_path, processor_name):
                        if dry_run:
                            print(f"    Would process with {processor_name}")
                        else:
                            print(f"    Processing with {processor_name}...")

                            # Mark as processing
                            await state_manager.mark_processing_start(note_info.note_path, processor_name)

                            # Process the note
                            result = await processor_registry.process_note(processor_name, note_info, parsed_note)

                            # Update state
                            await state_manager.mark_processing_complete(note_info.note_path, processor_name, result)

                            processing_results.append(result)

                            if result.success:
                                print(f"   SUCCESS: {processor_name}: {result.message}")
                            else:
                                print(f"   ERROR: {processor_name}: {result.message}")
                    else:
                        print(f"     Skipping {processor_name} (already processed)")

            except Exception as e:
                logger.error(f"Error processing note {note_info.note_path}: {e}")
                print(f"   ERROR: Error: {e}")

        # Print summary
        print("\n Processing Summary:")
        print(f"    Notes scanned: {notes_processed}")
        print(f"    Notes with audio: {notes_with_audio}")

        if processing_results:
            successful = sum(1 for r in processing_results if r.success)
            failed = len(processing_results) - successful
            print(f"   SUCCESS: Successful: {successful}")
            print(f"   ERROR: Failed: {failed}")

            if failed > 0:
                print("\nERROR: Failed processing:")
                for result in processing_results:
                    if not result.success:
                        print(f"   - {result.processor_name}: {result.message}")

    except Exception as e:
        logger.error(f"Processing failed: {e}")
        print(f"ERROR: Processing failed: {e}")
        raise


def interpolate_env_vars(content: str) -> str:
    """Interpolate environment variables in configuration content"""

    def replace_env_var(match):
        var_name = match.group(1)
        return os.environ.get(var_name, match.group(0))

    return re.sub(r"\$\{([^}]+)\}", replace_env_var, content)


def validate_config_values(config: Dict[str, Any]) -> List[str]:
    """Validate configuration values for logical consistency"""
    errors = []

    processing = config.get("processing", {})

    # Validate concurrency_limit
    concurrency = processing.get("concurrency_limit", 5)
    if concurrency <= 0:
        errors.append(f"concurrency_limit must be positive, got {concurrency}")
    elif concurrency > 100:
        errors.append(f"concurrency_limit seems too high, got {concurrency}")

    # Validate timeout
    timeout = processing.get("timeout", 300)
    if timeout <= 0:
        errors.append(f"timeout must be positive, got {timeout}")
    elif timeout > 3600:
        errors.append(f"timeout seems too high, got {timeout}")

    # Validate retry_attempts
    retry_attempts = processing.get("retry_attempts", 3)
    if retry_attempts < 0:
        errors.append(f"retry_attempts must be non-negative, got {retry_attempts}")
    elif retry_attempts > 10:
        errors.append(f"retry_attempts seems too high, got {retry_attempts}")

    return errors


def validate_vault_path(config: Dict[str, Any]) -> Optional[str]:
    """Validate vault path exists and is accessible"""
    if not config.get("vault_path"):
        return "vault_path is required"

    vault_path_obj = Path(config["vault_path"])
    if not vault_path_obj.exists():
        return f"Vault path does not exist: {vault_path_obj}"

    if not vault_path_obj.is_dir():
        return f"Vault path is not a directory: {vault_path_obj}"

    return None


def validate_processors(config: Dict[str, Any]) -> List[str]:
    """Validate processor configurations"""
    errors = []
    processors = config.get("processors", {})

    if not processors:
        errors.append("No processors configured")
        return errors

    valid_processor_types = ["whisper", "local", "script", "custom", "custom_api"]

    for proc_name, proc_config in processors.items():
        if not isinstance(proc_config, dict):
            errors.append(f"Processor '{proc_name}' must be a configuration object")
            continue

        proc_type = proc_config.get("type")
        if not proc_type:
            errors.append(f"Processor '{proc_name}' missing 'type' field")
        elif proc_type not in valid_processor_types:
            errors.append(f"Processor '{proc_name}' has unknown type '{proc_type}'")

        # Validate processor-specific config
        if proc_type == "whisper":
            config_section = proc_config.get("config", {})
            if not config_section.get("api_key"):
                errors.append(f"Whisper processor '{proc_name}' missing api_key")

    return errors


def scan_vault_for_markdown(vault_path: Path, exclude_patterns: List[str]) -> List[Path]:
    """Scan vault for markdown files, applying exclusion patterns"""
    markdown_files = []

    for file_path in vault_path.rglob("*.md"):
        relative_path = file_path.relative_to(vault_path)

        # Check if file should be excluded
        excluded = False
        for pattern in exclude_patterns:
            if fnmatch.fnmatch(str(relative_path), pattern):
                excluded = True
                break

        if not excluded:
            markdown_files.append(file_path)

    return markdown_files


def scan_for_voice_attachments(markdown_files: List[Path], vault_path: Path) -> List[Dict[str, Any]]:
    """Scan markdown files for voice attachments"""
    files_with_audio = []

    # Common audio file extensions

    for md_file in markdown_files:
        try:
            with open(md_file, "r", encoding="utf-8") as f:
                content = f.read()

            # Extract frontmatter and content
            frontmatter = {}
            audio_files = []

            # Simple frontmatter extraction
            if content.startswith("---"):
                try:
                    parts = content.split("---", 2)
                    if len(parts) >= 3:
                        frontmatter_text = parts[1]
                        # Skip template syntax for now
                        if not re.search(r"<%.*%>", frontmatter_text):
                            frontmatter = yaml.safe_load(frontmatter_text) or {}
                        main_content = parts[2]
                    else:
                        main_content = content
                except Exception:
                    main_content = content
            else:
                main_content = content

            # Find audio file references
            # Pattern: [[filename.ext]] or ![[filename.ext]]
            audio_pattern = r"!?\[\[([^\]]+\.(mp3|wav|m4a|ogg|flac|aac|opus|webm))\]\]"
            matches = re.findall(audio_pattern, main_content, re.IGNORECASE)

            for match in matches:
                audio_file = match[0]
                audio_type = match[1].lower()

                # Check if audio file exists
                audio_path = vault_path / audio_file
                if not audio_path.exists():
                    # Try in attachments folder
                    audio_path = vault_path / "attachments" / audio_file

                audio_files.append(
                    {"file": audio_file, "type": audio_type, "exists": audio_path.exists(), "path": str(audio_path)}
                )

            if audio_files:
                files_with_audio.append(
                    {
                        "note_path": str(md_file.relative_to(vault_path)),
                        "audio_files": audio_files,
                        "state": frontmatter.get("processor_state", {}),
                    }
                )

        except Exception:
            # Skip files that can't be read
            continue

    return files_with_audio


if __name__ == "__main__":
    if sys.version_info < (3, 8):
        print("Python 3.8+ required")
        sys.exit(1)

    main()
