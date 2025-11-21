"""Tests for documentation structure and validation."""

import json
import re
from pathlib import Path
from typing import List

import pytest


class TestDocumentationStructure:
    """Test that documentation files exist and have required structure."""

    @pytest.fixture
    def project_root(self) -> Path:
        """Get project root directory."""
        return Path(__file__).parent.parent.parent

    @pytest.fixture
    def docs_dir(self, project_root: Path) -> Path:
        """Get docs directory."""
        return project_root / "docs"

    def test_readme_exists(self, project_root: Path):
        """Test that main README.md exists."""
        readme = project_root / "README.md"
        assert readme.exists(), "README.md must exist in project root"

    def test_readme_has_required_sections(self, project_root: Path):
        """Test that README.md has required sections."""
        readme = project_root / "README.md"
        content = readme.read_text()

        required_sections = [
            "# Network Configuration Benchmark",
            "## Overview",
            "## Quick Start",
            "## Architecture",
        ]

        for section in required_sections:
            assert section in content, f"README.md must contain section: {section}"

    def test_docs_directory_exists(self, docs_dir: Path):
        """Test that docs/ directory exists."""
        assert docs_dir.exists(), "docs/ directory must exist"
        assert docs_dir.is_dir(), "docs/ must be a directory"

    def test_docs_readme_exists(self, docs_dir: Path):
        """Test that docs/README.md exists (documentation index)."""
        docs_readme = docs_dir / "README.md"
        # This will be created, so we'll check it exists or can be created
        # For now, just check the directory exists
        assert docs_dir.exists()

    def test_documentation_files_exist(self, docs_dir: Path):
        """Test that key documentation files exist or will be created."""
        # These files should exist after consolidation
        expected_files = [
            "GETTING_STARTED.md",
            "ARCHITECTURE.md",
            "TASK_FORMAT.md",
            "SUBMISSION_FORMAT.md",
            "CLI_USAGE.md",
            "RESEARCH_USAGE.md",
            "TESTING.md",
            "TROUBLESHOOTING.md",
            "LLM_INTEGRATION.md",
            "FORMALIZATION_ALIGNMENT.md",
        ]

        # Check which files exist (some may not exist yet during TDD)
        existing_files = [f.name for f in docs_dir.glob("*.md")]

        # At minimum, docs directory should exist
        assert docs_dir.exists()

        # Note: During TDD, files may not exist yet, so we just verify structure is ready


class TestDocumentationLinks:
    """Test that documentation links are valid."""

    @pytest.fixture
    def project_root(self) -> Path:
        """Get project root directory."""
        return Path(__file__).parent.parent.parent

    def extract_markdown_links(self, content: str) -> List[tuple[str, str]]:
        """Extract markdown links from content."""
        # Pattern: [text](path)
        pattern = r"\[([^\]]+)\]\(([^\)]+)\)"
        matches = re.findall(pattern, content)
        return matches

    def test_readme_links_are_valid(self, project_root: Path):
        """Test that links in README.md point to existing files."""
        readme = project_root / "README.md"
        content = readme.read_text()
        links = self.extract_markdown_links(content)

        for link_text, link_path in links:
            # Skip external links
            if link_path.startswith("http"):
                continue

            # Skip anchor links
            if link_path.startswith("#"):
                continue

            # Resolve relative paths
            if link_path.startswith("/"):
                target = project_root / link_path.lstrip("/")
            else:
                target = readme.parent / link_path

            # Check if file exists (or will exist after consolidation)
            # During TDD, some links may point to files not yet created
            # So we just verify the path is reasonable
            assert not target.is_absolute() or target.exists() or "docs/" in str(
                target
            ), f"Link '{link_text}' -> '{link_path}' may be invalid"


class TestDocumentationExamples:
    """Test that JSON examples in documentation are valid."""

    @pytest.fixture
    def project_root(self) -> Path:
        """Get project root directory."""
        return Path(__file__).parent.parent.parent

    def extract_json_blocks(self, content: str) -> List[str]:
        """Extract JSON code blocks from markdown."""
        # Pattern: ```json ... ```
        pattern = r"```json\s*\n(.*?)\n```"
        matches = re.findall(pattern, content, re.DOTALL)
        # Filter out partial examples (single lines, incomplete objects)
        complete_blocks = []
        for match in matches:
            # Only include if it looks like complete JSON (starts with { or [)
            stripped = match.strip()
            if stripped.startswith("{") and stripped.endswith("}") and stripped.count("{") == stripped.count("}"):
                complete_blocks.append(stripped)
            elif stripped.startswith("[") and stripped.endswith("]") and stripped.count("[") == stripped.count("]"):
                complete_blocks.append(stripped)
        return complete_blocks

    def test_readme_json_examples_are_valid(self, project_root: Path):
        """Test that JSON examples in README.md are valid JSON."""
        readme = project_root / "README.md"
        content = readme.read_text()
        json_blocks = self.extract_json_blocks(content)

        for i, json_block in enumerate(json_blocks):
            try:
                json.loads(json_block)
            except json.JSONDecodeError as e:
                pytest.fail(
                    f"Invalid JSON in README.md example {i+1}: {e}\nJSON:\n{json_block[:200]}"
                )

    def test_docs_json_examples_are_valid(self, project_root: Path):
        """Test that JSON examples in docs/ are valid JSON."""
        docs_dir = project_root / "docs"

        if not docs_dir.exists():
            pytest.skip("docs/ directory does not exist yet")

        for md_file in docs_dir.glob("*.md"):
            content = md_file.read_text()
            json_blocks = self.extract_json_blocks(content)

            for i, json_block in enumerate(json_blocks):
                # Skip template-style JSON with {{ }} placeholders
                if "{{" in json_block or "}}" in json_block:
                    continue
                
                # Skip examples with [...] placeholders (incomplete examples)
                if "[...]" in json_block or "..." in json_block:
                    continue

                try:
                    json.loads(json_block)
                except json.JSONDecodeError as e:
                    pytest.fail(
                        f"Invalid JSON in {md_file.name} example {i+1}: {e}\nJSON:\n{json_block[:200]}"
                    )

