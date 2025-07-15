---
broken_recordings:
- broken.m4a
broken_recordings_info:
  broken.m4a:
    error: Invalid audio file format
    timestamp: '2025-07-12T18:45:19.858405'
processor_state:
  summarize:
    error: '/opt/homebrew/Cellar/python@3.13/3.13.5/Frameworks/Python.framework/Versions/3.13/Resources/Python.app/Contents/MacOS/Python:
      can''t open file ''/Users/wese/Repos/obsidian-postprocessor/scripts/summarize.py'':
      [Errno 2] No such file or directory

      '
    message: Processing failed after 3 attempts
    processing_time: 0.0
    retry_count: 3
    status: failed
    timestamp: 1752520937.473696
  transcribe:
    error: 'HTTP 500: {"detail":{"status":"error","error":"Transcription process failed","code":"TRANSCRIPTION_FAILED","message":"Transcription
      process failed"}}'
    message: Processing failed after 3 attempts
    processing_time: 0.0
    retry_count: 3
    status: failed
    timestamp: 1752541207.413874
title: Broken Audio Test
---
# Broken Audio Test

This note contains a broken audio file that should be marked as broken instead of processed infinitely.

![[broken.m4a]]

The processor should handle this gracefully.
