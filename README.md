# Obsidian Post-Processor V2

A minimal, async-first tool for processing voice memos in Obsidian vaults. Automatically detects embedded voice recordings and executes configurable post-processing scripts while tracking state through frontmatter.

## High-Level Concept

The Obsidian Post-Processor V2 monitors an Obsidian vault for voice memos (embedded audio files like `![[Recording.m4a]]`) and executes custom post-processing scripts on them. It maintains a **stateless** design by tracking processed recordings in the frontmatter of each note, ensuring idempotent operations.

### Key Features

- **Minimal Dependencies**: Only PyYAML, aiofiles, and click
- **Async-First**: Built for concurrent processing from the ground up
- **Configuration-Driven**: YAML-based configuration with flexible exclusion patterns
- **Template-Safe**: Handles Obsidian templater syntax gracefully
- **Plugin Architecture**: Extensible processor system for different backends
- **Flexible Exclusions**: Glob pattern-based file and directory exclusion
- **Robust Error Handling**: Graceful handling of malformed frontmatter and template syntax

## Architecture

```
┌─────────────────────┐    ┌─────────────────────┐    ┌─────────────────────┐
│  Vault Scanner      │    │  Frontmatter        │    │  Processor          │
│  (Async)            │    │  Parser             │    │  Registry           │
│                     │    │                     │    │                     │
│  Find ![[*.m4a]]    │───▶│  Template-Safe      │───▶│  Plugin-Based       │
│  with exclusions    │    │  YAML Parsing       │    │  Async Processing   │
└─────────────────────┘    └─────────────────────┘    └─────────────────────┘
```

## Configuration

Configure via YAML file (`config.yaml`):

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
```

### Configuration Generation

Generate a default configuration file:

```bash
# Generate default config to stdout
python main.py --generate-config

# Save to file
python main.py --generate-config > config.yaml
```

## Usage

### Basic Usage

```bash
# Install dependencies
pip install -r requirements.txt

# Generate default configuration
python main.py --generate-config > config.yaml

# Edit config.yaml to set your vault path and preferences

# Validate configuration
python main.py --validate

# Dry run (analyze without processing)
python main.py --dry-run

# Process vault
python main.py

# Use custom config file
python main.py --config /path/to/custom-config.yaml

# Set log level
python main.py --log-level DEBUG
```

### Command-Line Configuration Overrides

All configuration options can be overridden via command-line flags:

```bash
# Override vault path
python main.py --vault-path /path/to/vault

# Override processing settings
python main.py --concurrency-limit 10 --timeout 120 --retry-attempts 5

# Add exclusion patterns
python main.py --exclude-pattern "drafts/**" --exclude-pattern "temp/**"

# Combine multiple overrides
python main.py \
  --config custom-config.yaml \
  --vault-path /path/to/vault \
  --concurrency-limit 8 \
  --timeout 180 \
  --exclude-pattern "archive/**" \
  --log-level DEBUG \
  --dry-run
```

### Available Command-Line Options

| Option | Type | Description |
|--------|------|-------------|
| `--config PATH` | Path | Path to configuration file |
| `--vault-path DIRECTORY` | Path | Path to Obsidian vault (overrides config) |
| `--concurrency-limit INTEGER` | Number | Maximum concurrent processing tasks |
| `--timeout INTEGER` | Seconds | Processing timeout in seconds |
| `--retry-attempts INTEGER` | Number | Number of retry attempts for failed processing |
| `--exclude-pattern TEXT` | Pattern | Exclusion pattern (can be used multiple times) |
| `--log-level LEVEL` | Choice | Set logging level (debug, info, warning, error) |
| `--dry-run` | Flag | Show what would be processed without executing |
| `--validate` | Flag | Validate configuration and exit |
| `--generate-config` | Flag | Generate default configuration to stdout |

### Docker Usage

```bash
# Build image
docker build -t obsidian-postprocessor .

# Generate default config
docker run obsidian-postprocessor --generate-config > config.yaml

# Run container with config file
docker run -v "/path/to/your/vault:/vault" \
  -v "$PWD/config.yaml:/app/config.yaml" \
  obsidian-postprocessor

# Run dry-run with command-line overrides
docker run -v "/path/to/your/vault:/vault" \
  -v "$PWD/config.yaml:/app/config.yaml" \
  obsidian-postprocessor \
  --vault-path /vault \
  --concurrency-limit 8 \
  --timeout 180 \
  --exclude-pattern "templates/**" \
  --log-level DEBUG \
  --dry-run

# Run without config file using only command-line options
docker run -v "/path/to/your/vault:/vault" \
  obsidian-postprocessor \
  --vault-path /vault \
  --concurrency-limit 5 \
  --timeout 300 \
  --retry-attempts 3 \
  --exclude-pattern "templates/**" \
  --exclude-pattern "archive/**" \
  --log-level INFO

# Validate configuration
docker run -v "/path/to/your/vault:/vault" \
  obsidian-postprocessor \
  --vault-path /vault \
  --validate
```

## Template-Safe Frontmatter Handling

V2 gracefully handles Obsidian templater syntax and malformed frontmatter:

```yaml
---
title: "<%tp.date.now()%>"
tags: [{{tag}}]
dynamic: <%tp.system.prompt()%>
---
```

**Template syntax is preserved**, not parsed as YAML. The processor will:
- Skip parsing template variables like `<%tp.date.now()%>`
- Preserve `{{variable}}` syntax
- Handle malformed YAML gracefully
- Continue processing other notes on errors

## State Management

The tool tracks processed recordings in frontmatter using the `postprocessor` section:

```yaml
---
title: "Meeting Notes"
postprocessor:
  transcribe:
    status: "completed"
    timestamp: "2024-01-01T12:00:00Z"
    files:
      - "recording.m4a"
---

Here are my voice memos:

![[recording.m4a]]
```

## Example Workflow

1. **Async Vault Scanning**: Scan vault for notes with voice attachments (`![[*.m4a]]`, `![[*.mp3]]`, etc.)
2. **Exclusion Filtering**: Skip notes matching exclusion patterns (templates, archives, etc.)
3. **Template-Safe Parsing**: Parse frontmatter while preserving template syntax
4. **State Check**: Check `postprocessor` section for already processed recordings
5. **Concurrent Processing**: Execute processors on new recordings with configurable concurrency
6. **State Update**: Mark recordings as processed in frontmatter
7. **Error Handling**: Retry failed operations with exponential backoff

## Voice Memo Transcription

The default post-processing script uses a Whisper HTTP API to transcribe voice memos and add transcripts to your notes. No API keys required!

### Setup

1. Ensure your Whisper API server is running and accessible (default: `http://host.docker.internal:8020`)
2. The post-processor will connect to the external API endpoint for transcription

### How it works

1. **Automatic Language Detection**: Detects language from filename patterns (`recording_en.m4a`, `meeting_de.wav`)
2. **HTTP API Transcription**: Uploads audio files to the Whisper API endpoint for transcription
3. **Note Update**: Adds the transcript to your note after the voice memo embed

### Configuration Options

You can customize the transcription process with environment variables:

- `WHISPER_MODEL`: Model size (tiny, base, small, medium, large) - default: `small`
- `WHISPER_LANGUAGE`: Force specific language (e.g., en, de, fr) - default: auto-detect
- `WHISPER_API_URL`: API endpoint URL - default: `http://host.docker.internal:8020`

### Example Result

Before processing:
```markdown
---
title: Meeting Notes
---

Here's my voice memo from the meeting:

![[Recording_en_20250711132921.m4a]]
```

After processing:
```markdown
---
title: Meeting Notes
processed_recordings:
  - "Recording_en_20250711132921.m4a"
---

Here's my voice memo from the meeting:

![[Recording_en_20250711132921.m4a]]

> **Transcript:**
> This is the transcript of your voice memo. The meeting covered three main topics: project timeline, budget allocation, and team assignments.
```

### Custom Post-Processing Script Interface

If you want to use a different post-processing script, it should accept:

```bash
python your_script.py <note_path> <voice_file_path>
```

Environment variables available to script:
- `VAULT_PATH`: Path to the vault
- `LOG_LEVEL`: Current log level
- `WHISPER_MODEL`: Whisper model size (tiny, base, small, medium, large)
- `WHISPER_LANGUAGE`: Force specific language (e.g., en, de, fr)
- `WHISPER_API_URL`: HTTP API endpoint for transcription (default: `http://host.docker.internal:8020`)

## Development

### Project Structure

```
obsidian-postprocessor/
├── src/
│   ├── config.py                 # Configuration management
│   ├── voice_memo_detector.py    # Voice memo detection
│   ├── state_manager.py          # Stateless state management
│   ├── runner.py                 # Script execution
│   └── processor.py              # Main processor class
├── processor/
│   └── add_transcript_to_voicememo.py  # Your post-processing script
├── testvault/                    # Test vault
├── tests/                        # Test suite
├── main.py                       # Entry point
├── requirements.txt              # Dependencies
├── Dockerfile                    # Container definition
├── .pre-commit-config.yaml       # Pre-commit hooks configuration
└── .flake8                       # Linting configuration
```

### Development Setup

1. **Clone and setup environment:**
   ```bash
   git clone <repository-url>
   cd obsidian-postprocessor
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   # or venv\Scripts\activate  # Windows
   pip install -r requirements.txt
   ```

2. **Install development tools:**
   ```bash
   pip install pre-commit pytest coverage
   pre-commit install
   ```

3. **Run development commands:**
   ```bash
   # Run tests
   ./venv/bin/python -m pytest tests/

   # Run tests with coverage
   ./venv/bin/python -m pytest tests/ --cov=src/

   # Run linting
   ./venv/bin/python -m flake8 src/ tests/ main.py

   # Auto-format code
   ./venv/bin/python -m black src/ tests/ main.py

   # Sort imports
   ./venv/bin/python -m isort src/ tests/ main.py

   # Check CI pipeline status
   ./check_pipeline.sh
   ```

### Pre-commit Hooks

The project uses pre-commit hooks to ensure code quality:

- **Black**: Automatic code formatting (120 char line length)
- **isort**: Import sorting
- **flake8**: Linting with project configuration
- **Basic checks**: Trailing whitespace, YAML validation, large files
- **pytest**: Fast test execution with fail-fast

```bash
# Run pre-commit on all files
pre-commit run --all-files

# Run specific hook
pre-commit run black
pre-commit run flake8
```

### Code Quality Standards

- **Line length**: 120 characters (relaxed from default 79)
- **Import sorting**: isort with black profile
- **Type hints**: Encouraged for new code
- **Testing**: Comprehensive test coverage required
- **Documentation**: Docstrings for public methods

### Testing Strategy

```bash
# Run all tests
./venv/bin/python -m pytest tests/

# Run with coverage report
./venv/bin/python -m pytest tests/ --cov=src/ --cov-report=html

# Run specific test file
./venv/bin/python -m pytest tests/test_voice_memo_detector.py

# Run with verbose output
./venv/bin/python -m pytest tests/ -v

# Run single test function
./venv/bin/python -m pytest tests/test_config.py::TestConfig::test_default_config
```

### Continuous Integration

The project uses GitHub Actions for CI/CD:

- **Multi-platform testing**: Ubuntu, Windows, macOS
- **Python version matrix**: 3.9, 3.10, 3.11, 3.12, 3.13
- **Code quality**: Linting, formatting, security scanning
- **Docker publishing**: Automatic container builds and registry publishing
- **Integration testing**: End-to-end workflow validation

Check pipeline status: `./check_pipeline.sh`

### Docker Development

```bash
# Build development image
docker build -t obsidian-postprocessor:dev .

# Run with local vault
docker run -v "$PWD/testvault/test-vault:/vault" obsidian-postprocessor:dev --dry-run

# Pull published image from registry
docker pull ghcr.io/rwese/obsidian-postprocessor:latest
```

## Requirements

- Python 3.8+
- Minimal dependencies:
  - `pyyaml` - Configuration handling
  - `aiofiles` - Async file operations
  - `click` - CLI interface
  - `pytest-asyncio` - Async testing support

### Optional Dependencies

- OpenAI API key for Whisper transcription (set via `OPENAI_API_KEY` environment variable)
- Custom processing scripts as needed
