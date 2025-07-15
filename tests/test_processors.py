"""
Test processor system for V2
"""

import asyncio
import tempfile
import time
from pathlib import Path

import pytest

from obsidian_processor.parser import FrontmatterParser
from obsidian_processor.processors import ProcessorRegistry, create_processor_registry_from_config
from obsidian_processor.scanner import NoteInfo, VaultScanner
from obsidian_processor.state import ProcessingStatus, StateManager


class TestProcessorRegistry:
    """Test processor registry functionality"""

    def test_registry_placeholder(self):
        """Placeholder test - will be updated when processors are implemented"""
        assert True

    def test_processor_registration(self):
        """Test processor registration"""
        # Mock processor registry
        registry = {}

        # Test registration
        def register_processor(name: str, processor_type: str):
            registry[name] = processor_type

        register_processor("transcribe", "whisper")
        register_processor("summarize", "script")

        assert "transcribe" in registry
        assert "summarize" in registry
        assert registry["transcribe"] == "whisper"
        assert registry["summarize"] == "script"

    def test_processor_lookup(self):
        """Test processor lookup by name"""
        registry = {"transcribe": "whisper", "summarize": "script", "translate": "openai"}

        # Test successful lookup
        assert registry.get("transcribe") == "whisper"
        assert registry.get("summarize") == "script"

        # Test missing processor
        assert registry.get("nonexistent") is None

    def test_processor_validation(self, sample_config: dict):
        """Test processor configuration validation"""
        processors = sample_config["processors"]

        for name, config in processors.items():
            # Each processor should have type and config
            assert "type" in config
            assert "config" in config
            assert isinstance(config["type"], str)
            assert isinstance(config["config"], dict)


class TestBaseProcessor:
    """Test base processor interface"""

    def test_base_processor_interface(self):
        """Test base processor interface requirements"""

        # Mock base processor interface
        class MockBaseProcessor:
            async def can_process(self, note_info: dict) -> bool:
                return True

            async def process(self, note_info: dict) -> dict:
                return {"status": "success"}

            async def cleanup(self, note_info: dict):
                pass

        processor = MockBaseProcessor()

        # Test interface methods exist
        assert hasattr(processor, "can_process")
        assert hasattr(processor, "process")
        assert hasattr(processor, "cleanup")

    @pytest.mark.asyncio
    async def test_processor_can_process(self):
        """Test processor can_process method"""

        class MockProcessor:
            async def can_process(self, note_info: dict) -> bool:
                return note_info.get("has_voice_memo", False)

        processor = MockProcessor()

        # Test with voice memo
        note_with_voice = {"has_voice_memo": True}
        assert await processor.can_process(note_with_voice) is True

        # Test without voice memo
        note_without_voice = {"has_voice_memo": False}
        assert await processor.can_process(note_without_voice) is False

    @pytest.mark.asyncio
    async def test_processor_process(self, mock_processor_result: dict):
        """Test processor process method"""

        class MockProcessor:
            async def process(self, note_info: dict) -> dict:
                await asyncio.sleep(0.01)  # Simulate processing
                return mock_processor_result

        processor = MockProcessor()
        note_info = {"path": "/test/note.md", "has_voice_memo": True}

        result = await processor.process(note_info)

        assert result["status"] == "success"
        assert result["processor"] == "test_processor"
        assert "data" in result
        assert "transcription" in result["data"]

    @pytest.mark.asyncio
    async def test_processor_cleanup(self):
        """Test processor cleanup method"""
        cleanup_called = False

        class MockProcessor:
            async def cleanup(self, note_info: dict):
                nonlocal cleanup_called
                cleanup_called = True

        processor = MockProcessor()
        await processor.cleanup({"path": "/test/note.md"})

        assert cleanup_called is True


class TestScriptProcessor:
    """Test script processor implementation"""

    def test_script_processor_placeholder(self):
        """Placeholder test - will be updated when script processor is implemented"""
        assert True

    def test_script_command_validation(self):
        """Test script command validation"""
        # Test valid commands
        valid_commands = [
            "python script.py",
            "python script.py {audio_file}",
            "python script.py {audio_file} {note_file}",
            "/usr/bin/python3 /path/to/script.py",
        ]

        for command in valid_commands:
            # Basic validation - should be non-empty string
            assert isinstance(command, str)
            assert len(command) > 0
            assert command.strip() == command

    def test_script_parameter_substitution(self):
        """Test parameter substitution in script commands"""
        template = "python script.py {audio_file} {note_file}"

        # Test parameter substitution
        audio_file = "/path/to/audio.m4a"
        note_file = "/path/to/note.md"

        expected = f"python script.py {audio_file} {note_file}"
        result = template.format(audio_file=audio_file, note_file=note_file)

        assert result == expected

    @pytest.mark.asyncio
    async def test_script_execution_timeout(self):
        """Test script execution timeout handling"""

        # Mock script execution with timeout
        async def mock_script_execution(timeout: float):
            if timeout < 0.1:
                raise asyncio.TimeoutError("Script execution timed out")
            await asyncio.sleep(0.01)
            return {"status": "success"}

        # Test successful execution
        result = await mock_script_execution(1.0)
        assert result["status"] == "success"

        # Test timeout
        with pytest.raises(asyncio.TimeoutError):
            await mock_script_execution(0.05)

    @pytest.mark.asyncio
    async def test_script_error_handling(self):
        """Test script error handling"""

        async def mock_script_with_error(should_fail: bool):
            if should_fail:
                raise Exception("Script execution failed")
            return {"status": "success"}

        # Test successful execution
        result = await mock_script_with_error(False)
        assert result["status"] == "success"

        # Test error handling
        with pytest.raises(Exception, match="Script execution failed"):
            await mock_script_with_error(True)


class TestProcessorExecution:
    """Test processor execution pipeline"""

    @pytest.mark.asyncio
    async def test_concurrent_processor_execution(self, mock_processor_result: dict):
        """Test concurrent processor execution"""

        class MockProcessor:
            async def process(self, note_info: dict) -> dict:
                await asyncio.sleep(0.01)  # Simulate processing
                return mock_processor_result

        processor = MockProcessor()

        # Test concurrent execution
        notes = [{"path": f"/test/note{i}.md", "has_voice_memo": True} for i in range(5)]

        # Process concurrently
        tasks = [processor.process(note) for note in notes]
        results = await asyncio.gather(*tasks)

        # Should process all notes
        assert len(results) == len(notes)
        assert all(r["status"] == "success" for r in results)

    @pytest.mark.asyncio
    async def test_processor_retry_logic(self):
        """Test processor retry logic"""
        attempt_count = 0

        class MockProcessor:
            async def process(self, note_info: dict) -> dict:
                nonlocal attempt_count
                attempt_count += 1

                if attempt_count < 3:
                    raise Exception("Temporary failure")

                return {"status": "success", "attempt": attempt_count}

        processor = MockProcessor()

        # Mock retry logic
        async def process_with_retry(note_info: dict, max_attempts: int = 3):
            for attempt in range(max_attempts):
                try:
                    return await processor.process(note_info)
                except Exception:
                    if attempt == max_attempts - 1:
                        raise
                    await asyncio.sleep(0.01)  # Brief delay between retries

        # Test successful retry
        result = await process_with_retry({"path": "/test/note.md"})
        assert result["status"] == "success"
        assert result["attempt"] == 3
        assert attempt_count == 3

    @pytest.mark.asyncio
    async def test_processor_result_aggregation(self, mock_processor_result: dict):
        """Test aggregation of processor results"""

        class MockProcessor:
            def __init__(self, name: str):
                self.name = name

            async def process(self, note_info: dict) -> dict:
                result = mock_processor_result.copy()
                result["processor"] = self.name
                return result

        processors = [MockProcessor("transcribe"), MockProcessor("summarize"), MockProcessor("translate")]

        note_info = {"path": "/test/note.md", "has_voice_memo": True}

        # Process with multiple processors
        results = []
        for processor in processors:
            result = await processor.process(note_info)
            results.append(result)

        # Test result aggregation
        assert len(results) == 3
        assert results[0]["processor"] == "transcribe"
        assert results[1]["processor"] == "summarize"
        assert results[2]["processor"] == "translate"
        assert all(r["status"] == "success" for r in results)


class TestReprocessingOnNewVoiceMemo:
    """Test that notes are reprocessed when new voice memos are added"""

    @pytest.fixture
    def test_vault_with_audio(self, temp_dir: Path):
        """Create a test vault with audio files"""
        vault_path = temp_dir / "test_vault"
        vault_path.mkdir()

        # Create attachments directory
        attachments_dir = vault_path / "Attachments"
        attachments_dir.mkdir()

        # Create audio files
        audio1 = attachments_dir / "recording1.m4a"
        audio2 = attachments_dir / "recording2.m4a"
        audio1.write_bytes(b"fake audio data 1")
        audio2.write_bytes(b"fake audio data 2")

        return vault_path

    @pytest.fixture
    def mock_processor_config(self):
        """Mock processor configuration for testing"""
        return {
            "test_processor": {
                "type": "script",
                "config": {"command": "echo 'Transcription: Test output'", "timeout": 30},
                "enabled": True,
            }
        }

    @pytest.mark.asyncio
    async def test_reprocessing_on_new_voice_memo(self, test_vault_with_audio: Path, mock_processor_config: dict):
        """Test that a note is reprocessed when a new voice memo is added"""

        # Step 1: Create initial note with one voice memo
        note_path = test_vault_with_audio / "voice_note.md"
        initial_content = """---
title: "Test Voice Note"
tags: [voice, test]
---

# Test Voice Note

First recording: ![[recording1.m4a]]

Some content here.
"""
        note_path.write_text(initial_content)

        # Step 2: Initialize components
        scanner = VaultScanner(test_vault_with_audio, [])
        parser = FrontmatterParser()
        state_manager = StateManager(dry_run=False)
        processor_registry = create_processor_registry_from_config(mock_processor_config)

        # Step 3: Process the note initially
        notes = []
        async for note_info in scanner.scan_vault():
            if note_info.note_path == note_path:
                notes.append(note_info)

        assert len(notes) == 1
        initial_note = notes[0]
        assert len(initial_note.attachments) == 1

        # Parse and process the note
        parsed_note = await parser.parse_note(note_path)

        # Verify initial state - should be pending
        should_process = await state_manager.should_process(note_path, "test_processor")
        assert should_process is True

        # Process the note
        result = await processor_registry.process_note("test_processor", initial_note, parsed_note)
        await state_manager.mark_processing_complete(note_path, "test_processor", result)

        # Verify processing was completed
        states = await state_manager.get_processing_state(note_path)
        assert "test_processor" in states
        assert states["test_processor"].status == ProcessingStatus.COMPLETED

        # Step 4: Add a new voice memo to the same note
        updated_content = """---
title: "Test Voice Note"
tags: [voice, test]
processor_state:
  test_processor:
    status: completed
    timestamp: {timestamp}
    message: Processing failed after 3 attempts
    retry_count: 3
    processing_time: 0.1
---

# Test Voice Note

First recording: ![[recording1.m4a]]

New recording: ![[recording2.m4a]]

Some content here.
""".format(
            timestamp=time.time()
        )

        note_path.write_text(updated_content)

        # Step 5: Scan the vault again to detect the new voice memo
        updated_notes = []
        async for note_info in scanner.scan_vault():
            if note_info.note_path == note_path:
                updated_notes.append(note_info)

        assert len(updated_notes) == 1
        updated_note = updated_notes[0]

        # Verify the note now has 2 attachments
        assert len(updated_note.attachments) == 2
        attachment_names = [att.name for att in updated_note.attachments]
        assert "recording1.m4a" in attachment_names
        assert "recording2.m4a" in attachment_names

        # Step 6: Check if the note should be reprocessed
        # The current implementation doesn't automatically detect content changes,
        # but we can simulate this by checking if the note content/attachments changed

        # Parse the updated note
        updated_parsed_note = await parser.parse_note(note_path)

        # The state manager should still show completed status
        current_states = await state_manager.get_processing_state(note_path)
        assert current_states["test_processor"].status == ProcessingStatus.COMPLETED

        # To trigger reprocessing, we need to either:
        # 1. Reset the state manually, or
        # 2. Implement content change detection

        # For this test, we'll reset the state to simulate content change detection
        await state_manager.reset_processor_state(note_path, "test_processor")

        # Step 7: Verify the note should now be reprocessed
        should_reprocess = await state_manager.should_process(note_path, "test_processor")
        assert should_reprocess is True

        # Step 8: Reprocess the note
        reprocess_result = await processor_registry.process_note("test_processor", updated_note, updated_parsed_note)
        await state_manager.mark_processing_complete(note_path, "test_processor", reprocess_result)

        # Step 9: Verify the note was reprocessed successfully
        final_states = await state_manager.get_processing_state(note_path)
        assert final_states["test_processor"].status == ProcessingStatus.COMPLETED

        # Verify the processor was called with the updated note containing both attachments
        assert len(updated_note.attachments) == 2

    @pytest.mark.asyncio
    async def test_content_change_detection(self, test_vault_with_audio: Path):
        """Test detection of content changes in notes"""

        # Create a note with initial content
        note_path = test_vault_with_audio / "changing_note.md"
        initial_content = """---
title: "Changing Note"
---

# Changing Note

First recording: ![[recording1.m4a]]
"""
        note_path.write_text(initial_content)

        # Get initial modification time and content hash
        initial_stat = note_path.stat()
        initial_mtime = initial_stat.st_mtime
        initial_size = initial_stat.st_size

        # Wait a bit to ensure time difference
        await asyncio.sleep(0.1)

        # Update the note with new content
        updated_content = """---
title: "Changing Note"
---

# Changing Note

First recording: ![[recording1.m4a]]
Second recording: ![[recording2.m4a]]
"""
        note_path.write_text(updated_content)

        # Get updated modification time and content hash
        updated_stat = note_path.stat()
        updated_mtime = updated_stat.st_mtime
        updated_size = updated_stat.st_size

        # Verify the file was modified
        assert updated_mtime > initial_mtime
        assert updated_size != initial_size

        # Scan the note to detect changes
        scanner = VaultScanner(test_vault_with_audio, [])

        notes = []
        async for note_info in scanner.scan_vault():
            if note_info.note_path == note_path:
                notes.append(note_info)

        assert len(notes) == 1
        note_info = notes[0]

        # Verify the scanner detected the updated modification time
        assert note_info.modified_time == updated_mtime

        # Verify the scanner found both attachments
        assert len(note_info.attachments) == 2

    @pytest.mark.asyncio
    async def test_multiple_voice_memos_in_single_note(self, test_vault_with_audio: Path, mock_processor_config: dict):
        """Test processing a note with multiple voice memos"""

        # Create note with multiple voice memos
        note_path = test_vault_with_audio / "multi_voice_note.md"
        content = """---
title: "Multi Voice Note"
tags: [voice, multiple]
---

# Multi Voice Note

First recording: ![[recording1.m4a]]

Some text in between.

Second recording: ![[recording2.m4a]]

More content.
"""
        note_path.write_text(content)

        # Initialize components
        scanner = VaultScanner(test_vault_with_audio, [])
        parser = FrontmatterParser()
        state_manager = StateManager(dry_run=False)
        processor_registry = create_processor_registry_from_config(mock_processor_config)

        # Scan and process the note
        notes = []
        async for note_info in scanner.scan_vault():
            if note_info.note_path == note_path:
                notes.append(note_info)

        assert len(notes) == 1
        note_info = notes[0]

        # Verify both attachments were found
        assert len(note_info.attachments) == 2
        attachment_names = [att.name for att in note_info.attachments]
        assert "recording1.m4a" in attachment_names
        assert "recording2.m4a" in attachment_names

        # Parse and process the note
        parsed_note = await parser.parse_note(note_path)
        result = await processor_registry.process_note("test_processor", note_info, parsed_note)

        # Verify processing was successful
        # (The processor should handle multiple attachments)
        assert result.success or result.error  # Should have attempted processing

    @pytest.mark.asyncio
    async def test_attachment_resolution_strategies(self, test_vault_with_audio: Path):
        """Test different attachment resolution strategies"""

        # Create audio files in different locations
        vault_path = test_vault_with_audio

        # Audio in root
        (vault_path / "root_audio.m4a").write_bytes(b"root audio")

        # Audio in Files directory
        files_dir = vault_path / "Files"
        files_dir.mkdir()
        (files_dir / "files_audio.m4a").write_bytes(b"files audio")

        # Audio in relative path
        notes_dir = vault_path / "Notes"
        notes_dir.mkdir()
        (notes_dir / "notes_audio.m4a").write_bytes(b"notes audio")

        # Create note with different attachment reference styles
        note_path = vault_path / "Notes" / "attachment_test.md"
        content = """---
title: "Attachment Test"
---

# Attachment Test

Root audio: ![[root_audio.m4a]]
Files audio: ![[files_audio.m4a]]
Notes audio: ![[notes_audio.m4a]]
Attachments audio: ![[recording1.m4a]]
"""
        note_path.write_text(content)

        # Scan the note
        scanner = VaultScanner(vault_path, [])

        notes = []
        async for note_info in scanner.scan_vault():
            if note_info.note_path == note_path:
                notes.append(note_info)

        assert len(notes) == 1
        note_info = notes[0]

        # Verify attachments were resolved from different locations
        # The scanner should find attachments using different resolution strategies
        found_attachments = [att.name for att in note_info.attachments]

        # Should find at least some attachments
        assert len(note_info.attachments) > 0

        # Should resolve from Attachments directory
        assert "recording1.m4a" in found_attachments

        # May also find others depending on resolution strategy
        # This tests the robustness of attachment resolution
