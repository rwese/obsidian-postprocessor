# Implementation TODO

## Status: Foundation Complete ✅

The V2 foundation is complete with CLI, configuration, testing, and documentation.

## Core Implementation Needed

### 1. Configuration System - `obsidian_processor/config.py`
```python
# Load YAML config with environment variable interpolation
# Merge with command-line overrides
# Validate configuration schema
```

### 2. Vault Scanner - `obsidian_processor/scanner.py`
```python
# Async vault scanning
# Glob pattern exclusion
# Voice memo detection
# Incremental processing support
```

### 3. Frontmatter Parser - `obsidian_processor/parser.py`
```python
# Template-safe YAML parsing
# Handle <%tp.date.now()%> syntax
# Graceful error handling
# State extraction and updates
```

### 4. Processor System - `obsidian_processor/processors/`
```python
# Base processor interface
# Whisper API processor
# Script processor
# Error handling and retries
```

### 5. State Manager - `obsidian_processor/state.py`
```python
# Atomic frontmatter updates
# Processing state tracking
# Conflict resolution
```

## Implementation Order

1. **Start with config.py** - Foundation for all other components
2. **Add scanner.py** - Core vault scanning functionality
3. **Add parser.py** - Template-safe frontmatter handling
4. **Add processors/** - Processing pipeline
5. **Add state.py** - State management
6. **Wire together** - Integration in main.py

## Test-Driven Development

- 51 tests already exist and define expected behavior
- Tests will guide implementation
- Run `python -m pytest tests/` to validate implementation

## Ready-to-Use Components

- ✅ CLI with full configuration support
- ✅ Command-line overrides
- ✅ Configuration validation
- ✅ Test infrastructure
- ✅ Documentation
- ✅ Custom transcription API spec

## Current Working Features

```bash
# Generate configuration
python main.py --generate-config > config.yaml

# Validate configuration
python main.py --vault-path /path/to/vault --validate

# Show implementation status
python main.py --vault-path /path/to/vault --dry-run
```

The foundation is solid and implementation-ready!
