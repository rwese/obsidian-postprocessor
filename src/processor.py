"""
Main processor class for Obsidian Post-Processor.

Coordinates voice memo detection, state management, and script execution.
"""

import logging
import time
from pathlib import Path
from typing import Dict, List, Optional

from .config import Config
from .voice_memo_detector import VoiceMemoDetector
from .state_manager import StatelessStateManager
from .runner import ScriptRunner


logger = logging.getLogger(__name__)


class ObsidianProcessor:
    """Main processor class that coordinates all components."""
    
    def __init__(self, config: Config):
        self.config = config
        suppress_errors = config.frontmatter_error_level == 'SILENT'
        self.detector = VoiceMemoDetector(config.vault_path, config.voice_patterns, suppress_errors)
        self.state_manager = StatelessStateManager(config.vault_path, config.frontmatter_error_level)
        self.script_runner = ScriptRunner(config.processor_script_path)
        self._connected = False
    
    def connect(self) -> 'ObsidianProcessor':
        """Connect to vault and initialize components."""
        try:
            self.detector.connect()
            self.state_manager.connect()
            self._connected = True
            logger.info("ObsidianProcessor connected successfully")
            return self
        except Exception as e:
            logger.error(f"Failed to connect ObsidianProcessor: {e}")
            raise
    
    def process_vault(self, dry_run: bool = False) -> Dict[str, any]:
        """
        Process the entire vault for unprocessed voice memos.
        
        Args:
            dry_run: If True, only analyze without executing scripts
            
        Returns:
            Dictionary with processing results
        """
        if not self._connected:
            raise RuntimeError("Processor not connected. Call connect() first.")
        
        logger.info(f"Starting vault processing (dry_run={dry_run})")
        
        results = {
            'total_notes': 0,
            'notes_with_memos': 0,
            'total_recordings': 0,
            'processed_recordings': 0,
            'unprocessed_recordings': 0,
            'newly_processed': 0,
            'failed_processing': 0,
            'errors': []
        }
        
        try:
            # Step 1: Detect all voice memos
            logger.info("Detecting voice memos in vault...")
            notes_with_memos = self.detector.get_notes_with_voice_memos()
            
            # Show found notes
            if notes_with_memos:
                logger.info("Found notes:")
                for note_path, voice_files in notes_with_memos.items():
                    logger.info(f"  • {note_path} ({len(voice_files)} recording{'s' if len(voice_files) != 1 else ''})")
            else:
                logger.info("Found notes: None with voice memos")
            
            # Step 2: Verify voice files exist
            logger.info("Verifying voice files exist...")
            verified_notes = self.detector.verify_voice_files_exist(notes_with_memos)
            
            # Step 3: Get processing statistics
            stats = self.state_manager.get_processing_stats(verified_notes)
            results.update(stats)
            results['notes_with_memos'] = len(verified_notes)
            
            logger.info(f"Found {results['notes_with_memos']} notes with voice memos")
            logger.info(f"Total recordings: {results['total_recordings']}")
            logger.info(f"Already processed: {results['processed_recordings']}")
            logger.info(f"Unprocessed: {results['unprocessed_recordings']}")
            
            # Step 4: Process unprocessed recordings
            if not dry_run:
                logger.info("Processing unprocessed recordings...")
                processing_results = self._process_unprocessed_recordings(verified_notes)
                results.update(processing_results)
            else:
                logger.info("Dry run mode - skipping actual processing")
            
            logger.info(f"Vault processing completed. Newly processed: {results['newly_processed']}")
            return results
            
        except Exception as e:
            logger.error(f"Error during vault processing: {e}")
            results['errors'].append(str(e))
            return results
    
    def _process_unprocessed_recordings(self, notes_with_memos: Dict[str, List[str]]) -> Dict[str, int]:
        """
        Process all unprocessed recordings with robust error handling.
        
        Args:
            notes_with_memos: Dictionary mapping note paths to voice file lists
            
        Returns:
            Dictionary with processing results
        """
        results = {
            'newly_processed': 0,
            'failed_processing': 0
        }
        
        total_notes = len(notes_with_memos)
        processed_notes = 0
        
        for note_path, voice_files in notes_with_memos.items():
            processed_notes += 1
            logger.info(f"Processing note {processed_notes}/{total_notes}: {note_path}")
            
            try:
                # Get unprocessed recordings for this note
                unprocessed = self.state_manager.get_unprocessed_recordings(note_path, voice_files)
                
                if not unprocessed:
                    logger.debug(f"No unprocessed recordings in {note_path}")
                    continue
                
                logger.info(f"Processing {len(unprocessed)} recordings from {note_path}")
                
                # Process each unprocessed recording with timeout protection
                for i, voice_file in enumerate(unprocessed):
                    logger.info(f"Processing recording {i+1}/{len(unprocessed)}: {voice_file}")
                    
                    try:
                        # Process with timeout to prevent hanging
                        if self._process_single_recording(note_path, voice_file):
                            results['newly_processed'] += 1
                            logger.info(f"✓ Successfully processed: {voice_file}")
                        else:
                            results['failed_processing'] += 1
                            logger.error(f"✗ Failed to process: {voice_file}")
                            
                    except Exception as e:
                        logger.error(f"✗ Exception processing {voice_file}: {e}")
                        results['failed_processing'] += 1
                        # Continue with next recording, don't let one failure stop everything
                        continue
                        
            except Exception as e:
                logger.error(f"Critical error processing note {note_path}: {e}")
                # Count all unprocessed recordings in this note as failed
                try:
                    unprocessed = self.state_manager.get_unprocessed_recordings(note_path, voice_files)
                    results['failed_processing'] += len(unprocessed)
                except:
                    # If we can't even get the unprocessed count, assume all are failed
                    results['failed_processing'] += len(voice_files)
                # Continue with next note
                continue
        
        logger.info(f"Processing completed: {results['newly_processed']} successful, {results['failed_processing']} failed")
        return results
    
    def _process_single_recording(self, note_path: str, voice_file: str, max_retries: int = 3) -> bool:
        """
        Process a single voice recording with retry logic.
        
        Args:
            note_path: Path to the note file
            voice_file: Voice file name
            max_retries: Maximum number of retry attempts
            
        Returns:
            True if processing succeeded, False otherwise
        """
        for attempt in range(max_retries):
            try:
                # Get full paths
                note_full_path = self.config.vault_path / f"{note_path}.md"
                voice_full_path = self.detector.get_voice_file_path(note_path, voice_file)
                
                if attempt == 0:
                    logger.info(f"Processing: {voice_file} from {note_path}")
                else:
                    logger.info(f"Retry {attempt}/{max_retries-1}: {voice_file} from {note_path}")
                
                # Execute the processing script
                success = self.script_runner.run_script(
                    note_full_path,
                    voice_full_path,
                    env_vars=self._get_script_env_vars()
                )
                
                if success:
                    # Mark as processed in frontmatter
                    if self.state_manager.mark_recording_processed(note_path, voice_file):
                        logger.info(f"Successfully processed: {voice_file}")
                        return True
                    else:
                        logger.error(f"Failed to mark recording as processed: {voice_file}")
                        # This is a state management error, don't retry
                        return False
                else:
                    logger.warning(f"Script execution failed for: {voice_file} (attempt {attempt + 1}/{max_retries})")
                    if attempt < max_retries - 1:
                        # Wait a bit before retry
                        time.sleep(1)
                    continue
                    
            except Exception as e:
                logger.error(f"Error processing recording {voice_file} (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    # Wait a bit before retry
                    time.sleep(1)
                    continue
                else:
                    # Final attempt failed
                    return False
        
        # After all retries failed, mark the recording as broken
        logger.error(f"Failed to process {voice_file} after {max_retries} attempts - marking as broken")
        
        # Mark as broken with error information
        broken_success = self.state_manager.mark_recording_broken(
            note_path, 
            voice_file, 
            f"Processing failed after {max_retries} attempts"
        )
        
        if broken_success:
            logger.warning(f"Marked {voice_file} as broken to prevent future processing attempts")
        else:
            logger.error(f"Failed to mark {voice_file} as broken")
        
        return False
    
    def _get_script_env_vars(self) -> Dict[str, str]:
        """Get environment variables for script execution."""
        return {
            'VAULT_PATH': str(self.config.vault_path),
            'LOG_LEVEL': self.config.log_level
        }
    
    def get_vault_status(self) -> Dict[str, any]:
        """
        Get current vault status without processing.
        
        Returns:
            Dictionary with vault status information
        """
        if not self._connected:
            raise RuntimeError("Processor not connected. Call connect() first.")
        
        try:
            # Get all voice memos
            notes_with_memos = self.detector.get_notes_with_voice_memos()
            
            # Show found notes
            if notes_with_memos:
                logger.info("Found notes:")
                for note_path, voice_files in notes_with_memos.items():
                    logger.info(f"  • {note_path} ({len(voice_files)} recording{'s' if len(voice_files) != 1 else ''})")
            else:
                logger.info("Found notes: None with voice memos")
            
            verified_notes = self.detector.verify_voice_files_exist(notes_with_memos)
            
            # Get processing statistics
            stats = self.state_manager.get_processing_stats(verified_notes)
            
            # Add vault information
            status = {
                'vault_path': str(self.config.vault_path),
                'processor_script': str(self.config.processor_script_path),
                'voice_patterns': self.config.voice_patterns,
                'notes_with_memos': len(verified_notes),
                **stats
            }
            
            return status
            
        except Exception as e:
            logger.error(f"Error getting vault status: {e}")
            return {'error': str(e)}
    
    def process_specific_note(self, note_path: str, dry_run: bool = False) -> Dict[str, any]:
        """
        Process a specific note for voice memos.
        
        Args:
            note_path: Relative path to the note within the vault
            dry_run: If True, only analyze without executing scripts
            
        Returns:
            Dictionary with processing results
        """
        if not self._connected:
            raise RuntimeError("Processor not connected. Call connect() first.")
        
        logger.info(f"Processing specific note: {note_path} (dry_run={dry_run})")
        
        results = {
            'note_path': note_path,
            'voice_recordings': [],
            'processed_recordings': [],
            'unprocessed_recordings': [],
            'newly_processed': 0,
            'failed_processing': 0,
            'errors': []
        }
        
        try:
            # Check if note exists (try with and without .md extension)
            note_full_path = self.config.vault_path / f"{note_path}.md"
            if not note_full_path.exists():
                note_full_path = self.config.vault_path / note_path
                if not note_full_path.exists():
                    error_msg = f"Note not found: {note_path}"
                    logger.error(error_msg)
                    results['errors'].append(error_msg)
                    return results
                else:
                    # Use the note path without .md extension for obsidiantools
                    note_path = note_path.replace('.md', '')
            else:
                # Use the note path without .md extension for obsidiantools
                note_path = note_path.replace('.md', '')
            
            # Extract voice recordings from this note
            voice_files = self.detector._extract_voice_files_from_note(note_path)
            results['voice_recordings'] = voice_files
            
            if not voice_files:
                logger.info(f"No voice recordings found in {note_path}")
                return results
            
            # Verify voice files exist
            verified_files = []
            for voice_file in voice_files:
                voice_path = self.detector.get_voice_file_path(note_path, voice_file)
                if voice_path.exists():
                    verified_files.append(voice_file)
                else:
                    logger.warning(f"Voice file not found: {voice_path}")
            
            if not verified_files:
                logger.warning(f"No valid voice files found for {note_path}")
                return results
            
            # Get processing status
            processed = self.state_manager.get_processed_recordings(note_path)
            unprocessed = self.state_manager.get_unprocessed_recordings(note_path, verified_files)
            
            results['processed_recordings'] = processed
            results['unprocessed_recordings'] = unprocessed
            
            # Process unprocessed recordings
            if not dry_run and unprocessed:
                logger.info(f"Processing {len(unprocessed)} recordings from {note_path}")
                
                for voice_file in unprocessed:
                    if self._process_single_recording(note_path, voice_file):
                        results['newly_processed'] += 1
                    else:
                        results['failed_processing'] += 1
            
            return results
            
        except Exception as e:
            logger.error(f"Error processing note {note_path}: {e}")
            results['errors'].append(str(e))
            return results