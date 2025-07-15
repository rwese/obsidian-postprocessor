---
obsidian-postprocessor:
  version: '1.0'
  voice-memos:
    test.m4a:
      model: small
      status: processed
      updated_at: '2025-07-14T16:15:50.000495+00:00'
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
    timestamp: 1752520967.559395
  transcribe:
    error: 'Error code: 401 - {''error'': {''message'': ''Incorrect API key provided:
      ${OPENAI*****KEY}. You can find your API key at https://platform.openai.com/account/api-keys.'',
      ''type'': ''invalid_request_error'', ''param'': None, ''code'': ''invalid_api_key''}}'
    message: Processing failed after 3 attempts
    processing_time: 0.0
    retry_count: 3
    status: failed
    timestamp: 1752520964.436546
title: Voice Memo in Notes Folder
---
This is a voice memo in the Notes subfolder.

![[test.m4a]]

> **Transcript:**
> Das ist ein Test eines Dictats, Punkt 1 funktioniert, Punkt 2 funktioniert nicht.


This should be detected by the voice memo detector.
