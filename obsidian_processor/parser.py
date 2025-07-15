"""Note parsing and frontmatter handling for Obsidian Post-Processor V2."""

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import yaml

logger = logging.getLogger(__name__)


@dataclass
class ParsedNote:
    """Parsed note with frontmatter and content."""

    path: Path
    frontmatter: Dict[str, Any]
    content: str
    has_frontmatter: bool
    raw_frontmatter: Optional[str] = None


class FrontmatterParser:
    """Robust frontmatter parser with template syntax tolerance."""

    def __init__(self):
        # Pattern to match frontmatter block
        self.frontmatter_pattern = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL | re.MULTILINE)

        # Template syntax patterns to handle gracefully
        self.template_patterns = [
            re.compile(r"<%.*?%>"),  # Templater syntax
            re.compile(r"\{\{.*?\}\}"),  # Handlebars/Mustache
            re.compile(r"\{\%.*?\%\}"),  # Jinja2
        ]

    async def parse_note(self, note_path: Path) -> ParsedNote:
        """Parse a note file and extract frontmatter and content."""
        try:
            content = note_path.read_text(encoding="utf-8")
            frontmatter, has_frontmatter, raw_frontmatter = self._extract_frontmatter(content)

            return ParsedNote(
                path=note_path,
                frontmatter=frontmatter,
                content=content,
                has_frontmatter=has_frontmatter,
                raw_frontmatter=raw_frontmatter,
            )

        except (OSError, IOError) as e:
            logger.error(f"Error reading note {note_path}: {e}")
            raise
        except UnicodeDecodeError as e:
            logger.error(f"Unicode decode error in note {note_path}: {e}")
            raise

    def _extract_frontmatter(self, content: str) -> Tuple[Dict[str, Any], bool, Optional[str]]:
        """Extract frontmatter from note content."""
        match = self.frontmatter_pattern.match(content)

        if not match:
            return {}, False, None

        raw_frontmatter = match.group(1)

        # Try to parse YAML with different strategies
        frontmatter = self._parse_yaml_with_fallback(raw_frontmatter)

        return frontmatter, True, raw_frontmatter

    def _parse_yaml_with_fallback(self, raw_yaml: str) -> Dict[str, Any]:
        """Parse YAML with fallback strategies for template syntax."""
        # Strategy 1: Try direct parsing
        try:
            result = yaml.safe_load(raw_yaml)
            if result is None:
                return {}
            return result if isinstance(result, dict) else {}
        except yaml.YAMLError:
            pass

        # Strategy 2: Try with template placeholders
        try:
            sanitized = self._sanitize_template_syntax(raw_yaml)
            result = yaml.safe_load(sanitized)
            if result is None:
                return {}
            return result if isinstance(result, dict) else {}
        except yaml.YAMLError:
            pass

        # Strategy 3: Line-by-line parsing
        try:
            return self._parse_yaml_line_by_line(raw_yaml)
        except Exception as e:
            logger.warning(f"Failed to parse frontmatter: {e}")
            return {}

    def _sanitize_template_syntax(self, yaml_content: str) -> str:
        """Replace template syntax with safe placeholder values."""
        sanitized = yaml_content

        # Replace templater syntax with placeholders
        sanitized = re.sub(r"<%.*?%>", '"__TEMPLATE_PLACEHOLDER__"', sanitized)
        sanitized = re.sub(r"\{\{.*?\}\}", '"__TEMPLATE_PLACEHOLDER__"', sanitized)
        sanitized = re.sub(r"\{\%.*?\%\}", '"__TEMPLATE_PLACEHOLDER__"', sanitized)

        return sanitized

    def _parse_yaml_line_by_line(self, yaml_content: str) -> Dict[str, Any]:
        """Parse YAML line by line, skipping problematic lines."""
        result = {}
        current_key = None
        current_value = []

        for line in yaml_content.split("\n"):
            line = line.strip()

            if not line or line.startswith("#"):
                continue

            # Check if this is a key-value pair
            if ":" in line and not line.startswith(" "):
                # Save previous key if exists
                if current_key:
                    result[current_key] = self._parse_value("\n".join(current_value))

                # Parse new key
                parts = line.split(":", 1)
                current_key = parts[0].strip()
                current_value = [parts[1].strip()] if len(parts) > 1 and parts[1].strip() else []

            elif current_key and line.startswith(" "):
                # Continuation of previous value
                current_value.append(line)
            else:
                # Skip problematic lines
                logger.debug(f"Skipping problematic YAML line: {line}")

        # Process final key
        if current_key:
            result[current_key] = self._parse_value("\n".join(current_value))

        return result

    def _parse_value(self, value_str: str) -> Any:
        """Parse a single YAML value with template awareness."""
        value_str = value_str.strip()

        if not value_str:
            return None

        # Check if it contains template syntax
        if any(pattern.search(value_str) for pattern in self.template_patterns):
            return value_str  # Return as-is for template values

        # Try to parse as YAML
        try:
            return yaml.safe_load(value_str)
        except yaml.YAMLError:
            return value_str  # Return as string if parsing fails

    def get_processing_state(self, frontmatter: Dict[str, Any]) -> Dict[str, Any]:
        """Extract processing state from frontmatter."""
        return frontmatter.get("processor_state", {})

    def has_processor_state(self, frontmatter: Dict[str, Any], processor_name: str) -> bool:
        """Check if note has state for a specific processor."""
        processor_state = self.get_processing_state(frontmatter)
        return processor_name in processor_state

    def get_processor_status(self, frontmatter: Dict[str, Any], processor_name: str) -> Optional[str]:
        """Get status of a specific processor."""
        processor_state = self.get_processing_state(frontmatter)
        return processor_state.get(processor_name)

    def should_process(self, frontmatter: Dict[str, Any], processor_name: str) -> bool:
        """Determine if note should be processed by a specific processor."""
        status = self.get_processor_status(frontmatter, processor_name)

        # Process if no status or status is 'pending' or 'failed'
        return status in [None, "pending", "failed"]

    def extract_attachments_from_content(self, content: str) -> list:
        """Extract attachment references from note content."""
        attachments = []

        # Pattern to match various attachment formats
        patterns = [
            r"!\[\[([^\]]+\.(m4a|mp3|wav|flac|aac|ogg|opus))\]\]",  # Obsidian wiki links
            r"!\[.*?\]\(([^\)]+\.(m4a|mp3|wav|flac|aac|ogg|opus))\)",  # Markdown links
            r'<audio[^>]*src=["\']([^"\']+\.(m4a|mp3|wav|flac|aac|ogg|opus))["\'][^>]*>',  # HTML audio
        ]

        for pattern in patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    attachments.append(match[0])
                else:
                    attachments.append(match)

        return attachments

    def create_backup_frontmatter(self, frontmatter: Dict[str, Any]) -> Dict[str, Any]:
        """Create a backup of current frontmatter state."""
        import time

        backup = frontmatter.copy()
        backup["_backup_timestamp"] = time.time()

        return backup

    def validate_frontmatter(self, frontmatter: Dict[str, Any]) -> list:
        """Validate frontmatter structure and return list of issues."""
        issues = []

        # Check for required fields structure
        if "processor_state" in frontmatter:
            processor_state = frontmatter["processor_state"]
            if not isinstance(processor_state, dict):
                issues.append("processor_state must be a dictionary")

        # Check for invalid characters in keys
        for key in frontmatter.keys():
            if not isinstance(key, str):
                issues.append(f"Frontmatter key must be string: {key}")
            elif any(char in key for char in [":", "[", "]", "{", "}"]):
                issues.append(f"Frontmatter key contains invalid characters: {key}")

        return issues


async def parse_note_async(note_path: Path) -> ParsedNote:
    """Convenience function to parse a single note."""
    parser = FrontmatterParser()
    return await parser.parse_note(note_path)
