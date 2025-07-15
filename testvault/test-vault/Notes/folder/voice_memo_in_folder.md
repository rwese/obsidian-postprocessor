---
processed_recordings:
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
    timestamp: 1752520974.7757409
  transcribe:
    message: Successfully transcribed test.m4a
    output: Das ist ein Test eines Dictats, Punkt 1 funktioniert, Punkt 2 funktioniert
      nicht.
    processing_time: 50.75555467605591
    retry_count: 0
    status: completed
    timestamp: 1752541055.064128
title: Voice Memo in Nested Folder
---
This is a voice memo in a nested subfolder Notes/folder/.

![[test.m4a]]



> **Transcript:**
> Das ist ein Test eines Dictats, Punkt 1 funktioniert, Punkt 2 funktioniert nicht.



This should also be detected by the voice memo detector.
