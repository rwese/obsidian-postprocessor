# Docker Usage Guide

This guide explains how to use the Obsidian Post-Processor V2 with Docker for automated voice memo transcription.

## Quick Start

### 1. Pull the Docker Image

```bash
docker pull ghcr.io/rwese/obsidian-postprocessor:latest
```

### 2. Basic Usage

```bash
docker run -v /path/to/your/obsidian/vault:/vault \
  -v /path/to/your/config.yaml:/app/config.yaml \
  ghcr.io/rwese/obsidian-postprocessor:latest
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `VAULT_PATH` | Path to Obsidian vault | `/vault` |
| `LOG_LEVEL` | Logging level (DEBUG, INFO, WARNING, ERROR) | `INFO` |
| `OPENAI_API_KEY` | OpenAI API key for Whisper (if using OpenAI) | - |

### Config File

Create a `config.yaml` file for your transcription service:

```yaml
# For self-hosted Whisper API
vault_path: "/vault"

exclude_patterns:
  - "**/*.sync-conflict*"
  - "templates/**"
  - "archive/**"
  - "**/*.template.md"
  - "**/.*"

processing:
  concurrency_limit: 1
  retry_attempts: 3
  retry_delay: 1.0
  timeout: 300

processors:
  transcribe:
    type: "custom_api"
    config:
      api_url: "https://whisper.nas.nope.at/transcribe"
      timeout: 300
      model: "medium"
      language: "auto"

logging:
  level: "INFO"
  format: "structured"
```

## Usage Examples

### 1. Process Voice Memos (Default)

```bash
docker run -v /home/user/MyVault:/vault \
  -v /home/user/config.yaml:/app/config.yaml \
  ghcr.io/rwese/obsidian-postprocessor:latest
```

### 2. Dry Run (Preview Only)

```bash
docker run -v /home/user/MyVault:/vault \
  -v /home/user/config.yaml:/app/config.yaml \
  ghcr.io/rwese/obsidian-postprocessor:latest \
  --dry-run
```

### 3. Custom Vault Path

```bash
docker run -v /home/user/MyVault:/myvault \
  -e VAULT_PATH=/myvault \
  -v /home/user/config.yaml:/app/config.yaml \
  ghcr.io/rwese/obsidian-postprocessor:latest
```

### 4. Debug Mode

```bash
docker run -v /home/user/MyVault:/vault \
  -v /home/user/config.yaml:/app/config.yaml \
  -e LOG_LEVEL=DEBUG \
  ghcr.io/rwese/obsidian-postprocessor:latest \
  --log-level debug
```

### 5. Using OpenAI Whisper

```bash
docker run -v /home/user/MyVault:/vault \
  -v /home/user/openai-config.yaml:/app/config.yaml \
  -e OPENAI_API_KEY=sk-your-api-key \
  ghcr.io/rwese/obsidian-postprocessor:latest
```

**OpenAI Config Example:**
```yaml
vault_path: "/vault"
processors:
  transcribe:
    type: "whisper"
    config:
      api_key: "${OPENAI_API_KEY}"
      model: "whisper-1"
      language: "auto"
```

## Docker Compose

Create a `docker-compose.yml` for easier management:

```yaml
version: '3.8'

services:
  obsidian-processor:
    image: ghcr.io/rwese/obsidian-postprocessor:latest
    volumes:
      - /path/to/your/vault:/vault
      - ./config.yaml:/app/config.yaml
    environment:
      - LOG_LEVEL=INFO
      - VAULT_PATH=/vault
    restart: "no"  # Run once, don't restart
```

Run with:
```bash
docker-compose up
```

## Automation

### Cron Job Example

Add to your crontab for automatic processing:

```bash
# Process voice memos every 15 minutes
*/15 * * * * docker run --rm -v /home/user/MyVault:/vault -v /home/user/config.yaml:/app/config.yaml ghcr.io/rwese/obsidian-postprocessor:latest
```

### Systemd Timer

Create `/etc/systemd/system/obsidian-processor.service`:
```ini
[Unit]
Description=Obsidian Voice Memo Processor
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
ExecStart=/usr/bin/docker run --rm \
  -v /home/user/MyVault:/vault \
  -v /home/user/config.yaml:/app/config.yaml \
  ghcr.io/rwese/obsidian-postprocessor:latest
User=user
Group=user
```

Create `/etc/systemd/system/obsidian-processor.timer`:
```ini
[Unit]
Description=Run Obsidian Processor every 15 minutes
Requires=obsidian-processor.service

[Timer]
OnCalendar=*:0/15
Persistent=true

[Install]
WantedBy=timers.target
```

Enable and start:
```bash
sudo systemctl enable obsidian-processor.timer
sudo systemctl start obsidian-processor.timer
```

## Troubleshooting

### Volume Permissions

If you encounter permission issues:

```bash
# Fix ownership (replace 1000:1000 with your user:group)
sudo chown -R 1000:1000 /path/to/your/vault

# Or run with current user
docker run --user $(id -u):$(id -g) \
  -v /path/to/your/vault:/vault \
  -v /path/to/config.yaml:/app/config.yaml \
  ghcr.io/rwese/obsidian-postprocessor:latest
```

### Check Logs

```bash
# Run with debug logging
docker run -v /path/to/vault:/vault \
  -v /path/to/config.yaml:/app/config.yaml \
  ghcr.io/rwese/obsidian-postprocessor:latest \
  --log-level debug
```

### Validate Configuration

```bash
# Test configuration without processing
docker run -v /path/to/vault:/vault \
  -v /path/to/config.yaml:/app/config.yaml \
  ghcr.io/rwese/obsidian-postprocessor:latest \
  --validate
```

## File Processing

### Supported Audio Formats
- MP3, WAV, M4A, FLAC, OGG, WMA, AAC
- MP4, MOV, AVI, MKV (video files with audio)

### Note Processing
- Scans for `![[audio_file.m4a]]` or `![description](audio_file.m4a)` in notes
- Adds transcription as quoted block below audio reference
- Stores processing state in note frontmatter
- Skips already processed files unless they've changed

### Example Note Transform

**Before:**
```markdown
# Voice Memo - 2024-01-15

Quick thoughts on the project:

![[recording_20240115.m4a]]

Need to follow up on this.
```

**After:**
```markdown
---
processor_state:
  transcribe:
    status: completed
    timestamp: 1705123456.789
    message: Successfully transcribed recording_20240115.m4a
    processing_time: 12.5
---

# Voice Memo - 2024-01-15

Quick thoughts on the project:

![[recording_20240115.m4a]]

> **Transcript:**
> This is a quick voice memo about the project. We need to implement the new feature by next week and coordinate with the design team.

Need to follow up on this.
```

## Security Considerations

- Mount vault as read-write for transcription insertion
- API keys passed via environment variables only
- No persistent storage of credentials in container
- Network access required for external transcription APIs
- Consider using Docker secrets for production deployments

## Performance Tips

- Use local/self-hosted Whisper API for better performance
- Set appropriate timeout values based on audio length
- Monitor disk space for large vaults
- Use `--dry-run` to preview processing scope
- Process during off-peak hours for large vaults

## Support

For issues and questions:
- GitHub Issues: https://github.com/rwese/obsidian-postprocessor/issues
- Documentation: See main README.md
- Configuration examples: See `config.yaml` in repository