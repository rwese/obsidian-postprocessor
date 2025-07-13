# Bug Report: Reprocessing Issue After Frontmatter Removal

## Summary
When a user manually removes the `processed_recordings` field from a note's frontmatter, the audio files should become available for reprocessing. However, there appears to be an issue where files that were previously processed don't get reprocessed even after their processing status is removed from the frontmatter.

## Bug Description
**Expected Behavior:**
1. Audio file gets processed and marked in frontmatter as processed
2. User manually removes `processed_recordings` field from frontmatter
3. On next run, audio file should be detected as unprocessed and get reprocessed

**Actual Behavior:**
Audio files that had their processing status manually removed from frontmatter are not being reprocessed.

## Reproduction Steps
1. Create a note with an embedded audio file: `![[Recording.webm]]`
2. Run the post-processor to process the audio file
3. Verify the file is marked as processed in frontmatter:
   ```yaml
   ---
   processed_recordings:
     - Recording.webm
   ---
   ```
4. Manually edit the note and remove the `processed_recordings` field from frontmatter
5. Run the post-processor again
6. **BUG**: The audio file is not reprocessed

## Technical Analysis

### Root Cause Investigation Needed
The issue likely lies in one of these areas:

1. **Vault State Caching**: The obsidiantools vault connection might be caching the old frontmatter state
2. **State Manager Logic**: The `get_unprocessed_recordings()` method might not be correctly identifying files as unprocessed after frontmatter changes
3. **File Detection**: The voice memo detector might not be re-scanning files properly

### Key Code Components to Investigate
- `StatelessStateManager.get_processed_recordings()` - Does this correctly read updated frontmatter?
- `StatelessStateManager.get_unprocessed_recordings()` - Does this correctly calculate unprocessed files?
- Vault reconnection logic - Are frontmatter changes being picked up?

## Test Case Added
A comprehensive test case has been added in `tests/test_state_manager.py`:
- `test_reprocessing_after_frontmatter_removal()` - Tests the complete workflow of processing, frontmatter removal, and reprocessing

## Debugging Steps
To debug this issue, run with enhanced logging:
```bash
export LOG_LEVEL=DEBUG
export DEBUG_VOICE_DETECTION=true
python main.py --dry-run
```

This will provide detailed output about:
- Voice file detection
- Frontmatter parsing
- Processing state determination
- File discovery process

## Priority
**High** - This affects the core functionality and user workflow when manually managing processing state.

## Workarounds
Until fixed, users can:
1. Delete the entire frontmatter section instead of just the `processed_recordings` field
2. Rename the audio file and embed the new name
3. Use the `--validate` flag to check if files are being detected correctly

## Related Files
- `src/state_manager.py` - State management and frontmatter handling
- `src/voice_memo_detector.py` - Voice file detection logic
- `tests/test_state_manager.py` - Test coverage including new regression test
- `main.py` - Entry point and processing orchestration
