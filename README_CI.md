# CI/CD Pipeline Guide

## Pipeline Status Monitoring

Use the included script to efficiently check GitHub Actions status:

```bash
./check_pipeline.sh
```

This script provides:
- Latest workflow run status
- Job-by-job breakdown
- Docker publish status
- Direct links to full details

## Docker Image

The project automatically publishes Docker images to GitHub Container Registry when changes are pushed to `main`.

### Pull and Run

```bash
# Pull the latest image
docker pull ghcr.io/rwese/obsidian-postprocessor:latest

# Test the container
docker run --rm ghcr.io/rwese/obsidian-postprocessor:latest --help
docker run --rm ghcr.io/rwese/obsidian-postprocessor:latest --config

# Run with your vault (example)
docker run --rm \
  -v /path/to/your/vault:/vault \
  -v /path/to/your/processor.py:/app/processor/add_transcript_to_voicememo.py \
  -e VAULT_PATH=/vault \
  -e PROCESSOR_SCRIPT_PATH=/app/processor/add_transcript_to_voicememo.py \
  ghcr.io/rwese/obsidian-postprocessor:latest --dry-run
```

## CI Pipeline Features

- **Multi-platform testing**: Ubuntu, Windows, macOS
- **Python version matrix**: 3.9-3.13
- **Comprehensive linting**: flake8, black, isort, mypy
- **Security scanning**: bandit, safety
- **Multi-architecture Docker**: linux/amd64, linux/arm64
- **Integration testing**: Full end-to-end validation

## Pipeline Jobs

1. **test**: Cross-platform Python testing
2. **lint**: Code quality and style checks
3. **security**: Security vulnerability scanning
4. **build**: Application build verification
5. **docker-publish**: Container image publishing (main branch only)
6. **integration**: Full integration testing

All jobs must pass before Docker image publication.
