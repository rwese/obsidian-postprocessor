# Obsidian Post-Processor

A stateless tool for processing voice memos in Obsidian vaults. Automatically detects embedded voice recordings and executes post-processing scripts while tracking state through frontmatter.

## High-Level Concept

The Obsidian Post-Processor monitors an Obsidian vault for voice memos (embedded audio files like `![[Recording.webm]]`) and executes custom post-processing scripts on them. It maintains a **stateless** design by tracking processed recordings in the frontmatter of each note, ensuring idempotent operations.

### Key Features

- **Stateless Operation**: No external databases or state files
- **Multiple Voice Memos**: Supports multiple voice recordings per note
- **Frontmatter Tracking**: Tracks processed recordings in YAML frontmatter
- **Configurable**: Environment variable-based configuration
- **Docker Ready**: Containerized for easy deployment
- **Comprehensive Logging**: Detailed logging for debugging

## Architecture

```
┌─────────────────────┐    ┌─────────────────────┐    ┌─────────────────────┐
│  Voice Memo         │    │  State Manager      │    │  Script Runner      │
│  Detector           │    │                     │    │                     │
│                     │    │  Frontmatter        │    │  Execute            │
│  Find ![[*.webm]]   │───▶│  Tracking           │───▶│  Post-processing    │
│  in notes           │    │                     │    │  Scripts            │
└─────────────────────┘    └─────────────────────┘    └─────────────────────┘
```

## Configuration

Configure via environment variables:

- `VAULT_PATH`: Path to Obsidian vault (default: `./testvault/test-vault`)
- `PROCESSOR_SCRIPT_PATH`: Path to post-processing script (default: `./processor/add_transcript_to_voicememo.py`)
- `VOICE_PATTERNS`: Voice file patterns (default: `*.webm,*.mp3,*.wav,*.m4a`)
- `STATE_METHOD`: State tracking method (default: `frontmatter`)
- `LOG_LEVEL`: Logging verbosity (default: `INFO`)
- `WATCH_MODE`: Enable file monitoring (default: `false`)
- `FRONTMATTER_ERROR_LEVEL`: Handle frontmatter parsing errors (default: `WARNING`, options: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`, `SILENT`)

## Usage

### Basic Usage

```bash
# Install dependencies
pip install -r requirements.txt

# Run processor
python main.py

# Dry run (analyze without processing)
python main.py --dry-run

# Process specific note
python main.py --note "Voice Memo.md"
```

### Docker Usage

```bash
# Build image
docker build -t obsidian-postprocessor .

# Run container (default: process entire vault)
docker run -v "/path/to/your/vault:/vault" \
  --network host \
  obsidian-postprocessor

# Show configuration
docker run -v "/path/to/your/vault:/vault" \
  --network host \
  obsidian-postprocessor --config

# Show vault status
docker run -v "/path/to/your/vault:/vault" \
  --network host \
  obsidian-postprocessor --status

# Run dry-run
docker run -v "/path/to/your/vault:/vault" \
  --network host \
  obsidian-postprocessor --dry-run

# Process specific note
docker run -v "/path/to/your/vault:/vault" \
  --network host \
  obsidian-postprocessor --note "Voice Memo"

# Run with custom environment variables
docker run -v "/path/to/your/vault:/vault" \
  --network host \
  -e LOG_LEVEL=DEBUG \
  -e VOICE_PATTERNS="*.webm,*.mp3" \
  -e FRONTMATTER_ERROR_LEVEL=SILENT \
  -e WHISPER_MODEL=medium \
  -e WHISPER_LANGUAGE=en \
  -e WHISPER_API_URL=http://host.docker.internal:8020 \
  obsidian-postprocessor --dry-run
```

**Note**: The default API URL uses `host.docker.internal` which allows Docker containers to access services running on the host machine.

## Frontmatter Error Handling

If you see warnings like:
```
Front matter not populated for Default Note.md: ParserError('while parsing a flow sequence'...
```

This indicates that some notes in your vault have malformed YAML frontmatter. The tool will skip these notes and continue processing. You can control how these errors are handled:

```bash
# Suppress frontmatter parsing warnings
FRONTMATTER_ERROR_LEVEL=SILENT python main.py

# Show frontmatter errors as debug messages
FRONTMATTER_ERROR_LEVEL=DEBUG python main.py

# Docker usage with suppressed warnings
docker run -v "/path/to/vault:/vault" \
  -e FRONTMATTER_ERROR_LEVEL=SILENT \
  obsidian-postprocessor
```

## State Management

The tool tracks processed recordings in frontmatter:

```yaml
---
processed_recordings:
  - "Recording 20250711123205.webm"
  - "Recording 20250711124305.webm"
---

Here are my voice memos:

![[Recording 20250711123205.webm]]
![[Recording 20250711124305.webm]]
```

## Example Workflow

1. **Detection**: Scan vault for notes with `![[*.webm]]` patterns
2. **State Check**: Check frontmatter for already processed recordings
3. **Processing**: Execute post-processing script on new recordings
4. **State Update**: Mark recordings as processed in frontmatter
5. **Logging**: Log all operations for debugging

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

- Python 3.9+
- Whisper HTTP API server (running at http://host.docker.internal:8020 by default)
- obsidiantools
- watchdog
- pyyaml
- requests

The Whisper API server should be running and accessible at the configured endpoint.
