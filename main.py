#!/usr/bin/env python3
"""
Obsidian Post-Processor Main Entry Point

A stateless tool for processing voice memos in Obsidian vaults.
"""

import argparse
import logging
import sys
import warnings
from pathlib import Path

from src.config import Config
from src.processor import ObsidianProcessor

# Suppress pandas FutureWarning from obsidiantools about DataFrame concatenation
warnings.filterwarnings(
    "ignore",
    message="The behavior of DataFrame concatenation with empty or all-NA entries is deprecated.*",
    category=FutureWarning,
    module="obsidiantools.*",
)

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))


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
    parser = argparse.ArgumentParser(description="Obsidian Post-Processor: Process voice memos in Obsidian vaults")

    parser.add_argument("--dry-run", action="store_true", help="Analyze vault without executing scripts")

    parser.add_argument("--note", type=str, help="Process specific note (relative path within vault)")

    parser.add_argument("--status", action="store_true", help="Show vault status without processing")

    parser.add_argument("--config", action="store_true", help="Show configuration and exit")

    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate configuration and script interface",
    )

    parser.add_argument(
        "--reprocess-broken",
        action="store_true",
        help="Reprocess all broken recordings (removes them from broken list)",
    )

    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode with structured logging and detailed output files",
    )

    parser.add_argument(
        "--metrics",
        action="store_true",
        help="Start Prometheus metrics server",
    )

    parser.add_argument(
        "--cleanup-logs",
        action="store_true",
        help="Clean up old detailed log files and exit",
    )

    args = parser.parse_args()

    try:
        # Load configuration
        config = Config()

        # Override config with command line arguments
        if args.debug:
            config.debug_mode = True
            config.structured_logging = True
            config.log_level = "DEBUG"

        # Set up logging
        setup_logging(config.log_level)
        logger = logging.getLogger(__name__)

        # Initialize structured logging if enabled
        structured_logger = None
        metrics_server = None
        detailed_output_writer = None

        if config.structured_logging or config.debug_mode:
            from src.structured_logger import DetailedOutputWriter, StructuredLogger

            structured_logger = StructuredLogger(
                name="obsidian-postprocessor",
                vault_path=config.vault_path,
                log_level=config.log_level,
                debug_mode=config.debug_mode,
            )
            detailed_output_writer = DetailedOutputWriter(config.vault_path)

            # Clean up old logs if requested
            if args.cleanup_logs:
                detailed_output_writer.cleanup_old_logs(config.log_cleanup_days)
                logger.info("Cleaned up old log files")
                return 0

        # Initialize metrics server if requested
        if args.metrics:
            from src.metrics import MetricsServer

            metrics_server = MetricsServer(config.prometheus_port)
            metrics_server.start()
            logger.info(f"Metrics server started on port {config.prometheus_port}")

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
            processor = ObsidianProcessor(config, structured_logger, detailed_output_writer)
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
        processor = ObsidianProcessor(config, structured_logger, detailed_output_writer).connect()

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
            results = processor.process_specific_note(
                args.note, dry_run=args.dry_run, reprocess_broken=args.reprocess_broken
            )

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
        results = processor.process_vault(dry_run=args.dry_run, reprocess_broken=args.reprocess_broken)

        # Display results
        print("\n=== Processing Results ===")
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

        # Update metrics from structured logger if available
        if metrics_server and structured_logger:
            metrics_server.get_metrics_collector().update_from_structured_logger(structured_logger)

        return 0

    except KeyboardInterrupt:
        logger.info("Processing interrupted by user")
        return 130
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        return 1
    finally:
        # Clean up metrics server if running
        if "metrics_server" in locals() and metrics_server:
            metrics_server.stop()


if __name__ == "__main__":
    sys.exit(main())
