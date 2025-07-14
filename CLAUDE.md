# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Obsidian Post-Processor is a stateless Python tool that automatically processes voice memos in Obsidian vaults. It detects embedded audio files and executes configurable post-processing scripts (primarily transcription via Whisper API) while maintaining state through YAML frontmatter.

## Development Commands

### Core Operations
- `python main.py --dry-run` - Analyze vault without processing files
- `python main.py --validate` - Validate configuration and scripts
- `python main.py --config path/to/config.yaml` - Use custom config
- `python main.py --log-level DEBUG` - Enable debug logging

### Testing
- `./venv/bin/python -m pytest tests/` - Run all tests
- `./venv/bin/python -m pytest tests/ --cov=src/` - Run tests with coverage
- `./venv/bin/python -m pytest tests/test_specific.py::test_function` - Run single test
- `./venv/bin/python -m pytest -v` - Verbose test output

### Code Quality
- `./check_pipeline.sh` - Check CI/CD pipeline status
- `./venv/bin/python -m flake8 src/ tests/` - Lint Python code
- `./venv/bin/python -m pytest --cov=src/ --cov-report=html` - Generate coverage report

### Docker
- `docker build -t obsidian-postprocessor .` - Build container
- `docker run -v /path/to/vault:/vault obsidian-postprocessor` - Run container

## Architecture

### Core Components
- **VoiceMemoDetector** (`src/voice_memo_detector.py`) - Scans notes for audio attachments
- **StateManager** (`src/state_manager.py`) - Manages processing state via YAML frontmatter
- **ScriptRunner** (`src/script_runner.py`) - Executes post-processing scripts
- **PostProcessor** (`src/post_processor.py`) - Main orchestration class
- **StructuredLogger** (`src/structured_logger.py`) - Enhanced logging with timing and detailed output

### Design Principles
- **Stateless**: No external databases - all state in note frontmatter
- **Idempotent**: Safe to run multiple times without side effects
- **Configurable**: YAML-based configuration for scripts and behavior
- **Observable**: Comprehensive logging and dry-run capabilities

### Key Patterns
- Configuration-driven script execution
- YAML frontmatter for state persistence
- Component-based architecture with clear separation of concerns
- Extensive error handling and validation

## Configuration

### Main Config (`config.yaml`)
```yaml
vault_path: "/path/to/obsidian/vault"
scripts:
  transcribe:
    command: "python scripts/transcribe.py {audio_file} {note_file}"
    timeout: 300
```

### Environment Variables
- `OPENAI_API_KEY` - For Whisper API transcription
- `LOG_LEVEL` - Set logging verbosity (DEBUG, INFO, WARNING, ERROR)

## Testing

### Test Structure
- `tests/test_voice_memo_detector.py` - Audio file detection logic
- `tests/test_state_manager.py` - Frontmatter state management
- `tests/test_script_runner.py` - Script execution and error handling
- `tests/test_post_processor.py` - End-to-end integration tests

### Test Data
- `tests/fixtures/` - Sample Obsidian notes and audio files
- `tests/test_vault/` - Mock vault structure for integration tests

## Development Workflow

### Making Changes
1. Run tests: `python -m pytest tests/`
2. Test with dry-run: `python main.py --dry-run`
3. Validate configuration: `python main.py --validate`
4. Check CI pipeline: `./check_pipeline.sh`

### Adding New Scripts
1. Create script in `scripts/` directory
2. Add configuration to `config.yaml`
3. Add tests in `tests/test_script_runner.py`
4. Update documentation

### Security Considerations
- Never commit API keys or sensitive configuration
- Scripts run with limited permissions
- Input validation for all file paths and commands
- Timeout enforcement for script execution

## Common Issues

### Script Execution Failures
- Check script permissions and dependencies
- Verify timeout settings in configuration
- Use `--log-level DEBUG` for detailed error messages

### State Management
- Frontmatter parsing errors indicate malformed YAML
- Missing state fields are automatically initialized
- State corruption requires manual frontmatter cleanup

### Performance
- Large vaults benefit from targeted directory processing
- Script timeouts prevent hanging on problematic files
- Dry-run mode useful for analyzing processing scope

## Code Quality & Linting

### Flake8 Configuration
The project uses relaxed linting rules defined in `.flake8`:
- Line length limit: 120 characters (more permissive than default 79)
- Configuration file automatically used by CI/CD pipeline

### Common Linting Pitfalls
**Multi-line String Formatting Syntax Error**
```python
# WRONG - Causes E999 SyntaxError:
f"Long string with {variable}"\n            f"continuation"

# CORRECT - Proper multi-line f-string:
f"Long string with {variable}"
f"continuation"

# ALTERNATIVE - Parentheses for implicit line joining:
(f"Long string with {variable} "
 f"continuation")
```

### Pipeline Commands
- `./venv/bin/python -m flake8 src/ tests/ main.py` - Lint with project config
- `./venv/bin/python -m black src/ tests/ main.py` - Auto-format code
- `./venv/bin/python -m isort src/ tests/ main.py` - Sort imports
- CI automatically uses `.flake8` configuration file
- Black and isort used for code formatting in pipeline

### Pre-commit Hooks Setup
```bash
pip install pre-commit
pre-commit install
```

**Pre-commit Hook Features:**
- Automatic code formatting with Black (120 char line length)
- Import sorting with isort
- Flake8 linting with project configuration
- Basic file checks (trailing whitespace, YAML validation, etc.)
- Fast pytest execution with fail-fast (-x flag)

**Manual Hook Execution:**
```bash
pre-commit run --all-files  # Run on all files
pre-commit run flake8       # Run specific hook
```

## Current Development State (2025-07-14)

### Recent Enhancements In Progress

**Enhanced Logging and Monitoring System**
- **Status**: Implementation in progress
- **Goal**: Add comprehensive error reporting, structured logging, and monitoring capabilities
- **Components Being Added**:
  - Structured logging with timing information (`src/structured_logger.py`)
  - Detailed output files next to processed notes for debugging
  - Debug mode with configurable log levels
  - Prometheus metrics endpoint for monitoring
  - Performance timing and operation tracking

**Key Issues Being Addressed**:
1. **Insufficient Error Reporting**: Current system lacks detailed error information when processing fails
2. **Limited Debugging Capabilities**: Need better visibility into processing pipeline
3. **No Performance Monitoring**: No metrics on processing times, success rates, etc.
4. **Missing Operation Context**: Logs don't provide enough context about what was happening when errors occur

### Implementation Progress

**Completed**:
- ✅ Structured logging system with timing and context (`src/structured_logger.py`)
- ✅ Detailed output file writer for debugging information
- ✅ Enhanced formatter with JSON output for debug mode
- ✅ Operation context tracking and metrics collection

**In Progress**:
- 🔄 Integration with existing components (processor, runner, state_manager)
- 🔄 Debug mode and enhanced configuration options
- 🔄 Prometheus metrics endpoint
- 🔄 Comprehensive test suite for new features

**Planned**:
- 📋 Update all components to use structured logging
- 📋 Add timing information to all operations
- 📋 Create detailed error output files for failed processing
- 📋 Add performance monitoring dashboard
- 📋 Comprehensive testing and validation

### For Future AI Agents

**When Working on This Project**:
1. **Use TodoWrite tool** to track progress and break down complex tasks
2. **Test thoroughly** - Run `python -m pytest tests/` before committing
3. **Maintain backward compatibility** - Don't break existing frontmatter structure
4. **Follow structured logging patterns** - Use StructuredLogger for all new logging
5. **Performance focus** - Add timing information to all operations
6. **Error handling** - Always provide detailed error context and recovery options

**Key Integration Points**:
- **ScriptRunner** (`src/runner.py`) - Needs structured logging for script execution
- **StateManager** (`src/state_manager.py`) - Needs timing and detailed error reporting
- **PostProcessor** (`src/processor.py`) - Main integration point for enhanced logging
- **Config** (`src/config.py`) - Add new configuration options for debug mode

**Testing Strategy**:
- Unit tests for each new component
- Integration tests for logging workflow
- Performance tests for timing accuracy
- Error simulation tests for debugging features

**Monitoring Requirements**:
- Processing success/failure rates
- Average processing times per file
- Script execution performance
- Error frequency and patterns
- Resource utilization metrics

### Environment Variables (Enhanced)
- `OPENAI_API_KEY` - For Whisper API transcription
- `LOG_LEVEL` - Set logging verbosity (DEBUG, INFO, WARNING, ERROR)
- `DEBUG_MODE` - Enable structured JSON logging and detailed output files
- `PROMETHEUS_PORT` - Port for metrics endpoint (default: 8000)
- `LOG_CLEANUP_DAYS` - Days to keep detailed log files (default: 7)

### New Development Commands
- `python main.py --debug` - Enable debug mode with structured logging
- `python main.py --metrics` - Start with Prometheus metrics endpoint
- `python main.py --cleanup-logs` - Clean up old detailed log files
- `python main.py --performance-test` - Run performance analysis
