"""
Tests for retry logic and error handling.
"""

import tempfile
import logging
import os
from pathlib import Path
from unittest.mock import Mock, patch, call
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from src.processor import ObsidianProcessor
from src.config import Config


class TestRetryLogic:
    """Test retry logic and error handling."""
    
    def create_test_vault_with_unprocessed(self, temp_dir):
        """Create a test vault with unprocessed recordings."""
        vault_path = Path(temp_dir) / 'vault'
        vault_path.mkdir()
        
        # Create a test processor script
        processor_path = vault_path / 'processor.py'
        processor_path.write_text("""#!/usr/bin/env python3
import sys
print(f"Processing {sys.argv[1]} with {sys.argv[2]}")
exit(0)
""")
        processor_path.chmod(0o755)
        
        # Note with unprocessed recording
        note1 = vault_path / 'Test Note.md'
        note1.write_text("""---
title: Test Note
---

This note has an unprocessed recording.

![[Recording001.webm]]
""")
        
        # Create the voice file
        voice_file = vault_path / 'Recording001.webm'
        voice_file.write_text("fake audio data")
        
        return vault_path, processor_path
    
    def test_retry_on_script_failure(self, caplog):
        """Test retry logic when script execution fails."""
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_path, processor_path = self.create_test_vault_with_unprocessed(temp_dir)
            
            # Set up config using environment variables
            with patch.dict(os.environ, {
                'VAULT_PATH': str(vault_path),
                'PROCESSOR_SCRIPT_PATH': str(processor_path),
                'VOICE_PATTERNS': '*.webm'
            }):
                config = Config()
                
                # Create processor
                processor = ObsidianProcessor(config)
                
                # Mock the script runner to fail first 2 attempts, succeed on 3rd
                with patch.object(processor.script_runner, 'run_script') as mock_run:
                    mock_run.side_effect = [False, False, True]  # Fail, Fail, Success
                    
                    # Connect processor
                    processor.connect()
                    
                    # Clear logs
                    caplog.clear()
                    caplog.set_level(logging.INFO)
                    
                    # Test single recording processing
                    result = processor._process_single_recording('Test Note', 'Recording001.webm')
                    
                    # Should succeed after retries
                    assert result is True
                    
                    # Should have called run_script 3 times
                    assert mock_run.call_count == 3
                    
                    # Check log messages for retry attempts
                    log_messages = [record.message for record in caplog.records]
                    assert any("Processing: Recording001.webm" in msg for msg in log_messages)
                    assert any("Retry 1/2: Recording001.webm" in msg for msg in log_messages)
                    assert any("Retry 2/2: Recording001.webm" in msg for msg in log_messages)
                    assert any("Successfully processed: Recording001.webm" in msg for msg in log_messages)
    
    def test_retry_exhausted_failure(self, caplog):
        """Test when all retry attempts are exhausted."""
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_path, processor_path = self.create_test_vault_with_unprocessed(temp_dir)
            
            # Set up config using environment variables
            with patch.dict(os.environ, {
                'VAULT_PATH': str(vault_path),
                'PROCESSOR_SCRIPT_PATH': str(processor_path),
                'VOICE_PATTERNS': '*.webm'
            }):
                config = Config()
                
                # Create processor
                processor = ObsidianProcessor(config)
                
                # Mock the script runner to always fail
                with patch.object(processor.script_runner, 'run_script') as mock_run:
                    mock_run.return_value = False  # Always fail
                    
                    # Connect processor
                    processor.connect()
                    
                    # Clear logs
                    caplog.clear()
                    caplog.set_level(logging.INFO)
                    
                    # Test single recording processing
                    result = processor._process_single_recording('Test Note', 'Recording001.webm')
                    
                    # Should fail after all retries
                    assert result is False
                    
                    # Should have called run_script 3 times (max retries)
                    assert mock_run.call_count == 3
                    
                    # Check log messages for all retry attempts
                    log_messages = [record.message for record in caplog.records]
                    assert any("Failed to process Recording001.webm after 3 attempts" in msg for msg in log_messages)
    
    def test_exception_handling_with_retry(self, caplog):
        """Test exception handling with retry logic."""
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_path, processor_path = self.create_test_vault_with_unprocessed(temp_dir)
            
            # Set up config using environment variables
            with patch.dict(os.environ, {
                'VAULT_PATH': str(vault_path),
                'PROCESSOR_SCRIPT_PATH': str(processor_path),
                'VOICE_PATTERNS': '*.webm'
            }):
                config = Config()
                
                # Create processor
                processor = ObsidianProcessor(config)
                
                # Mock the script runner to raise exception first 2 times, succeed on 3rd
                with patch.object(processor.script_runner, 'run_script') as mock_run:
                    mock_run.side_effect = [
                        Exception("Network error"),
                        Exception("Timeout error"),
                        True  # Success on 3rd attempt
                    ]
                    
                    # Connect processor
                    processor.connect()
                    
                    # Clear logs
                    caplog.clear()
                    caplog.set_level(logging.INFO)
                    
                    # Test single recording processing
                    result = processor._process_single_recording('Test Note', 'Recording001.webm')
                    
                    # Should succeed after handling exceptions
                    assert result is True
                    
                    # Should have called run_script 3 times
                    assert mock_run.call_count == 3
                    
                    # Check log messages for exception handling
                    log_messages = [record.message for record in caplog.records]
                    assert any("Error processing recording Recording001.webm" in msg for msg in log_messages)
    
    def test_robust_batch_processing(self, caplog):
        """Test robust batch processing doesn't get stuck on errors."""
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_path, processor_path = self.create_test_vault_with_unprocessed(temp_dir)
            
            # Create additional test files
            note2 = vault_path / 'Note2.md'
            note2.write_text("""---
title: Note 2
---

![[Recording002.webm]]
""")
            
            note3 = vault_path / 'Note3.md'
            note3.write_text("""---
title: Note 3
---

![[Recording003.webm]]
""")
            
            # Create voice files
            (vault_path / 'Recording002.webm').write_text("fake audio 2")
            (vault_path / 'Recording003.webm').write_text("fake audio 3")
            
            # Set up config using environment variables
            with patch.dict(os.environ, {
                'VAULT_PATH': str(vault_path),
                'PROCESSOR_SCRIPT_PATH': str(processor_path),
                'VOICE_PATTERNS': '*.webm'
            }):
                config = Config()
                
                # Create processor
                processor = ObsidianProcessor(config)
                
                # Mock script runner: fail first recording, succeed others
                with patch.object(processor.script_runner, 'run_script') as mock_run:
                    mock_run.side_effect = [
                        False, False, False,  # All 3 attempts for first recording fail
                        True,  # Second recording succeeds
                        True   # Third recording succeeds
                    ]
                    
                    # Connect processor
                    processor.connect()
                    
                    # Clear logs
                    caplog.clear()
                    caplog.set_level(logging.INFO)
                    
                    # Process entire vault
                    results = processor.process_vault(dry_run=False)
                    
                    # Should have processed 2 successfully, 1 failed
                    assert results['newly_processed'] == 2
                    assert results['failed_processing'] == 1
                    
                    # Should have tried all recordings and not gotten stuck
                    log_messages = [record.message for record in caplog.records]
                    assert any("Processing completed: 2 successful, 1 failed" in msg for msg in log_messages)
    
    def test_state_management_error_no_retry(self, caplog):
        """Test that state management errors don't trigger retries."""
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_path, processor_path = self.create_test_vault_with_unprocessed(temp_dir)
            
            # Set up config using environment variables
            with patch.dict(os.environ, {
                'VAULT_PATH': str(vault_path),
                'PROCESSOR_SCRIPT_PATH': str(processor_path),
                'VOICE_PATTERNS': '*.webm'
            }):
                config = Config()
                
                # Create processor
                processor = ObsidianProcessor(config)
                
                # Mock successful script execution but failed state management
                with patch.object(processor.script_runner, 'run_script') as mock_run, \
                     patch.object(processor.state_manager, 'mark_recording_processed') as mock_mark:
                    
                    mock_run.return_value = True  # Script succeeds
                    mock_mark.return_value = False  # State management fails
                    
                    # Connect processor
                    processor.connect()
                    
                    # Clear logs
                    caplog.clear()
                    
                    # Test single recording processing
                    result = processor._process_single_recording('Test Note', 'Recording001.webm')
                    
                    # Should fail without retry
                    assert result is False
                    
                    # Should have called run_script only once (no retry for state errors)
                    assert mock_run.call_count == 1
                    assert mock_mark.call_count == 1
                    
                    # Check log messages
                    log_messages = [record.message for record in caplog.records]
                    assert any("Failed to mark recording as processed" in msg for msg in log_messages)