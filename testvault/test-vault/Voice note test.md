---
processed_recordings:
- Recording 20250711132921.m4a
- test.m4a
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
    timestamp: 1752520959.2500532
  transcribe:
    message: Successfully transcribed test.m4a
    output: Das ist ein Test eines Dictats, Punkt 1 funktioniert, Punkt 2 funktioniert
      nicht.
    processing_time: 50.47162580490112
    retry_count: 0
    status: completed
    timestamp: 1752540760.952381
tags:
- voice-memo
- test
title: Voice note test
---
# Voice note test

This is a test note that demonstrates the voice memo processing issue.

The processor should be able to find this note even when running in different environments (Docker vs local).

![[test.m4a]]



> **Transcript:**
> Das ist ein Test eines Dictats, Punkt 1 funktioniert, Punkt 2 funktioniert nicht.

