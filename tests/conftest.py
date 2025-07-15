"""
Pytest configuration and fixtures for V2 tests
"""

import asyncio
import tempfile
from pathlib import Path
from typing import Generator

import pytest
import yaml


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for test files"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_config() -> dict:
    """Sample configuration for testing"""
    return {
        "vault_path": "/tmp/test_vault_fixture",
        "exclude_patterns": ["templates/**", "archive/**", "**/*.template.md", "**/.*"],
        "processing": {"concurrency_limit": 2, "retry_attempts": 3, "retry_delay": 1.0, "timeout": 60},
        "processors": {"test_processor": {"type": "script", "config": {"command": "echo 'test'"}}},
        "logging": {"level": "INFO", "format": "structured"},
    }


@pytest.fixture
def config_file(temp_dir: Path, sample_config: dict) -> Path:
    """Create a temporary config file"""
    config_path = temp_dir / "config.yaml"
    with open(config_path, "w") as f:
        yaml.dump(sample_config, f)
    return config_path


@pytest.fixture
def test_vault(temp_dir: Path) -> Path:
    """Create a test vault with various note types"""
    vault_path = temp_dir / "test_vault"
    vault_path.mkdir()

    # Create directories
    (vault_path / "daily").mkdir()
    (vault_path / "templates").mkdir()
    (vault_path / "archive").mkdir()
    (vault_path / "attachments").mkdir()

    # Create notes with voice memos
    note_with_voice = vault_path / "daily" / "2024-01-01.md"
    note_with_voice.write_text(
        """---
title: "Daily Note"
tags: [daily]
---

# Daily Note

Voice memo: ![[recording.m4a]]

Some other content.
"""
    )

    # Create template note (should be excluded)
    template_note = vault_path / "templates" / "daily.md"
    template_note.write_text(
        """---
title: "<%tp.date.now()%>"
tags: [template]
---

# Template Note

Template syntax: {{title}}
"""
    )

    # Create note without voice memo
    regular_note = vault_path / "regular.md"
    regular_note.write_text(
        """---
title: "Regular Note"
---

# Regular Note

Just text content.
"""
    )

    # Create processed note
    processed_note = vault_path / "processed.md"
    processed_note.write_text(
        """---
title: "Processed Note"
postprocessor:
  transcribe:
    status: "completed"
    timestamp: "2024-01-01T12:00:00Z"
---

# Processed Note

Voice memo: ![[recording.m4a]]

Transcription: "Hello world"
"""
    )

    # Create audio file
    audio_file = vault_path / "attachments" / "recording.m4a"
    audio_file.write_bytes(b"fake audio data")

    return vault_path


@pytest.fixture
def sample_note_content() -> str:
    """Sample note content with frontmatter"""
    return """---
title: "Test Note"
tags: [test, voice]
created: "2024-01-01"
---

# Test Note

This is a test note with a voice memo.

![[recording.m4a]]

Some additional content.
"""


@pytest.fixture
def malformed_frontmatter_cases() -> list:
    """Various malformed frontmatter cases for testing"""
    return [
        # Missing closing ---
        "---\ntitle: Test\n\nContent",
        # Invalid YAML
        "---\nkey: [unclosed\n---\nContent",
        # Template syntax
        "---\ntitle: <%tp.date.now()%>\ntags: [{{tag}}]\n---\nContent",
        # No frontmatter
        "# Just a title\n\nContent without frontmatter",
        # Empty frontmatter
        "---\n---\nContent",
        # Mixed indentation
        "---\nkey1: value1\n  key2: value2\n\tkey3: value3\n---\nContent",
    ]


@pytest.fixture
def event_loop():
    """Create an event loop for async tests"""
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_processor_result():
    """Mock processor result for testing"""
    return {
        "status": "success",
        "processor": "test_processor",
        "timestamp": "2024-01-01T12:00:00Z",
        "data": {"transcription": "Test transcription", "duration": 30.5},
    }
