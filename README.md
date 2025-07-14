# Obsidian Post-Processor V2

A minimal, async-first tool for processing voice memos and other attachments in Obsidian vaults. V2 provides a clean, configuration-driven, plugin-based architecture for reliable voice memo transcription.

## Features

- **Async-First Architecture**: Built for concurrent processing with configurable limits
- **Configuration-Driven**: YAML-based configuration with environment variable support
- **Template-Safe**: Handles Obsidian template syntax gracefully
- **Flexible Exclusion**: Glob pattern-based file exclusion
- **Useful Dry-Run**: Actually scans vault and shows what would be processed
- **Command-Line Overrides**: All configuration options available via CLI
- **Environment Variable Interpolation**: `${VARIABLE}` expansion in config files
- **Comprehensive Validation**: Validates configuration values and processor settings

## Quick Start

### 1. Setup Environment

```bash
# Clone and enter directory
git clone https://github.com/rwese/obsidian-postprocessor.git
cd obsidian-postprocessor

# Create virtual environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Optional: Setup direnv for automatic venv activation
direnv allow  # If you have direnv installed
```

### 2. Configuration

```bash
# Generate default configuration
python main.py --generate-config > config.yaml

# Edit config.yaml and set your vault path and API keys
# Or use environment variables and CLI overrides
```

### 3. Usage

```bash
# Validate configuration
python main.py --vault-path ~/Obsidian --validate

# Dry run (shows what would be processed)
python main.py --vault-path ~/Obsidian --dry-run

# Process voice memos (when core implementation is complete)
python main.py --vault-path ~/Obsidian
```

## Configuration

### YAML Configuration (`config.yaml`)

```yaml
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

# Logging configuration
logging:
  level: "INFO"
  file: "logs/processor.log"
  format: "structured"
```

### Environment Variables

Create a `.env` file (copy from `.env.example`):

```bash
# OpenAI API key for Whisper transcription
OPENAI_API_KEY=your_openai_api_key_here

# Optional: Custom transcription service
TRANSCRIPTION_API_URL=http://localhost:8080/transcribe
TRANSCRIPTION_API_KEY=your_custom_api_key

# Logging
LOG_LEVEL=INFO
```

### Command-Line Overrides

All configuration options can be overridden via command-line:

```bash
python main.py \
  --vault-path ~/Obsidian \
  --concurrency-limit 10 \
  --timeout 120 \
  --retry-attempts 5 \
  --exclude-pattern "archive/**" \
  --exclude-pattern "templates/**" \
  --log-level DEBUG \
  --dry-run
```

## CLI Usage

### Basic Commands

```bash
# Help
python main.py --help

# Generate default configuration
python main.py --generate-config

# Validate configuration
python main.py --validate

# Dry run (scan vault and show processing plan)
python main.py --dry-run

# Process vault (when implementation is complete)
python main.py
```

### Configuration Options

| Option | Description | Example |
|--------|-------------|---------|
| `--vault-path` | Path to Obsidian vault | `--vault-path ~/Obsidian` |
| `--config` | Configuration file path | `--config my-config.yaml` |
| `--concurrency-limit` | Max concurrent tasks | `--concurrency-limit 10` |
| `--timeout` | Processing timeout (seconds) | `--timeout 300` |
| `--retry-attempts` | Number of retry attempts | `--retry-attempts 3` |
| `--exclude-pattern` | Exclusion pattern (repeatable) | `--exclude-pattern "archive/**"` |
| `--log-level` | Logging level | `--log-level DEBUG` |
| `--dry-run` | Show processing plan | `--dry-run` |
| `--validate` | Validate configuration | `--validate` |
| `--generate-config` | Generate default config | `--generate-config` |

## Development

### Environment Setup

```bash
# Install development dependencies
pip install -r requirements.txt

# Setup pre-commit hooks
pre-commit install

# Run tests
python -m pytest tests/

# Run with coverage
python -m pytest tests/ --cov=main --cov-report=html
```

### Development Commands

```bash
# Linting
flake8 main.py tests/
black --check main.py tests/
isort --check-only main.py tests/

# Testing
python -m pytest tests/ -v
python -m pytest tests/ --cov=main

# Dry run on test data
python main.py --vault-path tests/fixtures/test_vault --dry-run
```

## Architecture

### V2 Design Principles

1. **Minimal Dependencies**: Only essential dependencies for maximum reliability
2. **Configuration-Driven**: All behavior controlled via YAML configuration
3. **Async-First**: Built for concurrent processing from the ground up
4. **Plugin-Based**: Extensible processor system for different processing types
5. **Robust Error Handling**: Graceful handling of template syntax and malformed data

### Current Implementation Status

✅ **Complete - Ready to Use:**
- CLI with full configuration support
- Command-line override hierarchy
- Configuration validation with bounds checking
- Environment variable interpolation
- Dry-run with actual vault scanning
- Comprehensive test suite (56 tests, 81% coverage)

⚠️ **Core Implementation Needed:**
- `obsidian_processor/config.py` - Configuration loading system
- `obsidian_processor/scanner.py` - Async vault scanning
- `obsidian_processor/parser.py` - Template-safe frontmatter parsing
- `obsidian_processor/processors.py` - Processor registry and implementations
- `obsidian_processor/state.py` - State management

See `spec/v2.md` for complete implementation specification.

## Custom Transcription Services

V2 supports custom transcription services. See `docs/custom-transcription-api.md` for the API specification and `examples/custom-transcription-server.py` for a complete example implementation.

## Migration from V1

V2 is a complete rewrite with breaking changes:
- Configuration format changed from environment variables to YAML
- Frontmatter structure simplified
- Script execution interface changed
- Removed dependency on obsidiantools

See `DEVELOPMENT_STATUS.md` for migration guidance.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Run the test suite
6. Submit a pull request

## License

This project is licensed under the MIT License. See LICENSE file for details.

## Support

- **Documentation**: See `docs/` directory
- **Issues**: GitHub Issues
- **Specifications**: See `spec/v2.md`
- **Examples**: See `examples/` directory
