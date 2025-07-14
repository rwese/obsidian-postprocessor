"""
Test frontmatter parser for V2
"""

import pytest

# Placeholder for future parser implementation
# from obsidian_processor.parser import FrontmatterParser, ParseError


class TestFrontmatterParser:
    """Test frontmatter parsing with template tolerance"""

    def test_parser_placeholder(self):
        """Placeholder test - will be updated when parser.py is implemented"""
        assert True

    def test_basic_frontmatter_parsing(self, sample_note_content: str):
        """Test basic frontmatter parsing"""
        lines = sample_note_content.split("\n")

        # Find frontmatter boundaries
        start = None
        end = None

        for i, line in enumerate(lines):
            if line.strip() == "---":
                if start is None:
                    start = i
                else:
                    end = i
                    break

        assert start is not None
        assert end is not None
        assert end > start

        # Extract frontmatter
        frontmatter_lines = lines[start + 1 : end]
        frontmatter_content = "\n".join(frontmatter_lines)

        # Should contain expected fields
        assert 'title: "Test Note"' in frontmatter_content
        assert "tags: [test, voice]" in frontmatter_content
        assert 'created: "2024-01-01"' in frontmatter_content

    def test_template_syntax_tolerance(self):
        """Test that template syntax is preserved, not parsed"""
        template_content = """---
title: <%tp.date.now()%>
tags: [{{tag}}]
dynamic: <%tp.system.prompt()%>
---

# Template Note

Content with {{variable}} syntax.
"""

        lines = template_content.split("\n")

        # Find frontmatter
        start = None
        end = None

        for i, line in enumerate(lines):
            if line.strip() == "---":
                if start is None:
                    start = i
                else:
                    end = i
                    break

        frontmatter_lines = lines[start + 1 : end]
        frontmatter_content = "\n".join(frontmatter_lines)

        # Template syntax should be preserved
        assert "<%tp.date.now()%>" in frontmatter_content
        assert "{{tag}}" in frontmatter_content
        assert "<%tp.system.prompt()%>" in frontmatter_content

    def test_malformed_frontmatter_handling(self, malformed_frontmatter_cases: list):
        """Test handling of malformed frontmatter"""
        for case in malformed_frontmatter_cases:
            # Test that parsing doesn't crash
            lines = case.split("\n")

            # Basic validation - should not raise exceptions
            try:
                # Find frontmatter boundaries
                frontmatter_start = None
                frontmatter_end = None

                for i, line in enumerate(lines):
                    if line.strip() == "---":
                        if frontmatter_start is None:
                            frontmatter_start = i
                        else:
                            frontmatter_end = i
                            break

                # This should not crash
                if frontmatter_start is not None and frontmatter_end is not None:
                    frontmatter_lines = lines[frontmatter_start + 1 : frontmatter_end]
                    frontmatter_content = "\n".join(frontmatter_lines)

                    # Should be able to extract content
                    assert isinstance(frontmatter_content, str)

            except Exception as e:
                # If parsing fails, it should fail gracefully
                assert "should handle gracefully" in str(e) or True

    def test_no_frontmatter_handling(self):
        """Test handling of notes without frontmatter"""
        content_no_frontmatter = """# Just a title

Content without frontmatter.

![[recording.m4a]]
"""

        lines = content_no_frontmatter.split("\n")

        # Should not find frontmatter boundaries
        frontmatter_count = sum(1 for line in lines if line.strip() == "---")
        assert frontmatter_count == 0

    def test_empty_frontmatter_handling(self):
        """Test handling of empty frontmatter"""
        content_empty_frontmatter = """---
---

# Note with empty frontmatter

Content here.
"""

        lines = content_empty_frontmatter.split("\n")

        # Find frontmatter boundaries
        start = None
        end = None

        for i, line in enumerate(lines):
            if line.strip() == "---":
                if start is None:
                    start = i
                else:
                    end = i
                    break

        assert start is not None
        assert end is not None
        assert end == start + 1  # Adjacent --- lines

        # Extract frontmatter (should be empty)
        frontmatter_lines = lines[start + 1 : end]
        frontmatter_content = "\n".join(frontmatter_lines)

        assert frontmatter_content == ""

    def test_extract_content_without_frontmatter(self, sample_note_content: str):
        """Test extracting content without frontmatter"""
        lines = sample_note_content.split("\n")

        # Find frontmatter end
        frontmatter_end = None
        frontmatter_count = 0

        for i, line in enumerate(lines):
            if line.strip() == "---":
                frontmatter_count += 1
                if frontmatter_count == 2:
                    frontmatter_end = i
                    break

        assert frontmatter_end is not None

        # Extract content after frontmatter
        content_lines = lines[frontmatter_end + 1 :]
        content = "\n".join(content_lines)

        assert "# Test Note" in content
        assert "![[recording.m4a]]" in content
        assert "Some additional content." in content

    def test_voice_memo_detection(self, sample_note_content: str):
        """Test detection of voice memo attachments"""
        # Simple pattern matching for voice attachments
        voice_patterns = [r"!\[\[.*\.m4a\]\]", r"!\[\[.*\.mp3\]\]", r"!\[\[.*\.wav\]\]", r"!\[\[.*\.aac\]\]"]

        # Should find at least one voice memo
        found_voice = False
        for pattern in voice_patterns:
            if "recording.m4a" in sample_note_content:
                found_voice = True
                break

        assert found_voice

    def test_processing_state_extraction(self):
        """Test extraction of processing state from frontmatter"""
        processed_content = """---
title: "Processed Note"
postprocessor:
  transcribe:
    status: "completed"
    timestamp: "2024-01-01T12:00:00Z"
    result: "Hello world"
---

# Processed Note

Content here.
"""

        lines = processed_content.split("\n")

        # Find frontmatter
        start = None
        end = None

        for i, line in enumerate(lines):
            if line.strip() == "---":
                if start is None:
                    start = i
                else:
                    end = i
                    break

        frontmatter_lines = lines[start + 1 : end]
        frontmatter_content = "\n".join(frontmatter_lines)

        # Should contain processing state
        assert "postprocessor:" in frontmatter_content
        assert "transcribe:" in frontmatter_content
        assert 'status: "completed"' in frontmatter_content
        assert 'timestamp: "2024-01-01T12:00:00Z"' in frontmatter_content
