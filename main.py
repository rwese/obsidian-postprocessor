#!/usr/bin/env python3
"""
Obsidian Post-Processor Main Entry Point

A stateless tool for processing voice memos in Obsidian vaults.
"""

import argparse
import logging
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.config import Config
from src.processor import ObsidianProcessor


def setup_logging(log_level: str):
    """Set up logging configuration."""
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
        ],
    )


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Obsidian Post-Processor: Process voice memos in Obsidian vaults"
    )

    parser.add_argument(
        "--dry-run", action="store_true", help="Analyze vault without executing scripts"
    )

    parser.add_argument(
        "--note", type=str, help="Process specific note (relative path within vault)"
    )

    parser.add_argument(
        "--status", action="store_true", help="Show vault status without processing"
    )

    parser.add_argument(
        "--config", action="store_true", help="Show configuration and exit"
    )

    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate configuration and script interface",
    )

    args = parser.parse_args()

    try:
        # Load configuration
        config = Config()

        # Set up logging
        setup_logging(config.log_level)
        logger = logging.getLogger(__name__)

        # Show configuration if requested
        if args.config:
            print(config)
            return 0

        # Validate configuration
        if args.validate:
            logger.info("Validating configuration...")
            config.validate()
            logger.info("Configuration validation passed")

            # Create processor and validate script interface
            processor = ObsidianProcessor(config)
            if processor.script_runner.validate_script_interface():
                logger.info("Script interface validation passed")
            else:
                logger.warning("Script interface validation failed")

            return 0

        # Validate configuration
        logger.info("Validating configuration...")
        config.validate()

        # Create and connect processor
        logger.info("Initializing processor...")
        processor = ObsidianProcessor(config).connect()

        # Show status if requested
        if args.status:
            logger.info("Getting vault status...")
            status = processor.get_vault_status()

            print("\n=== Vault Status ===")
            print(f"Vault Path: {status['vault_path']}")
            print(f"Processor Script: {status['processor_script']}")
            print(f"Voice Patterns: {status['voice_patterns']}")
            print(f"Notes with Memos: {status['notes_with_memos']}")
            print(f"Total Recordings: {status['total_recordings']}")
            print(f"Processed Recordings: {status['processed_recordings']}")
            print(f"Unprocessed Recordings: {status['unprocessed_recordings']}")

            return 0

        # Process specific note
        if args.note:
            logger.info(f"Processing specific note: {args.note}")
            results = processor.process_specific_note(args.note, dry_run=args.dry_run)

            print(f"\n=== Processing Results for {args.note} ===")
            print(f"Voice Recordings: {len(results['voice_recordings'])}")
            print(f"Processed Recordings: {len(results['processed_recordings'])}")
            print(f"Unprocessed Recordings: {len(results['unprocessed_recordings'])}")

            if not args.dry_run:
                print(f"Newly Processed: {results['newly_processed']}")
                print(f"Failed Processing: {results['failed_processing']}")

            if results["errors"]:
                print(f"Errors: {results['errors']}")
                return 1

            return 0

        # Process entire vault
        logger.info("Processing entire vault...")
        results = processor.process_vault(dry_run=args.dry_run)

        # Display results
        print(f"\n=== Processing Results ===")
        print(f"Notes with Memos: {results['notes_with_memos']}")
        print(f"Total Recordings: {results['total_recordings']}")
        print(f"Previously Processed: {results['processed_recordings']}")
        print(f"Unprocessed: {results['unprocessed_recordings']}")

        if not args.dry_run:
            print(f"Newly Processed: {results['newly_processed']}")
            print(f"Failed Processing: {results['failed_processing']}")

        if results["errors"]:
            print(f"Errors: {results['errors']}")
            return 1

        if args.dry_run:
            logger.info("Dry run completed - no changes made")
        else:
            logger.info("Processing completed")

        return 0

    except KeyboardInterrupt:
        logger.info("Processing interrupted by user")
        return 130
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
