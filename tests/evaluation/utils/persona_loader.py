"""
Persona loader for dataset generation.

Discovers and loads persona markdown files from the prompts directory.
"""

import re
from pathlib import Path
from dataclasses import dataclass
from typing import List


@dataclass
class Persona:
    """Represents a user persona for question generation."""
    id: str
    name: str
    content: str
    technical_level: str = "unknown"


class PersonaLoader:
    """Loads persona definitions from markdown files."""

    def __init__(self, prompts_dir: Path):
        """
        Initialize persona loader.

        Args:
            prompts_dir: Directory containing persona .md files
        """
        self.prompts_dir = Path(prompts_dir)

    def discover_personas(self) -> List[Persona]:
        """
        Discover all persona files in prompts directory.

        Returns:
            List of Persona objects
        """
        personas = []

        if not self.prompts_dir.exists():
            return personas

        for md_file in self.prompts_dir.glob("*.md"):
            # Skip README files (case-insensitive)
            if md_file.name.upper() == "README.MD":
                continue

            content = md_file.read_text(encoding='utf-8')

            persona = Persona(
                id=md_file.stem,
                name=self._parse_persona_name(content),
                content=content,
                technical_level=self._parse_technical_level(content)
            )
            personas.append(persona)

        return personas

    def _parse_persona_name(self, content: str) -> str:
        """
        Extract persona name from H1 header.

        Args:
            content: Markdown content

        Returns:
            Persona name or empty string
        """
        match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        if match:
            return match.group(1).strip()
        return ""

    def _parse_technical_level(self, content: str) -> str:
        """
        Extract technical level from markdown.

        Args:
            content: Markdown content

        Returns:
            Technical level (lowercase) or "unknown"
        """
        # Look for "## Technical Level" section
        match = re.search(
            r'##\s+Technical Level\s*\n(.+?)(?:\n##|\Z)',
            content,
            re.MULTILINE | re.DOTALL
        )

        if match:
            level_text = match.group(1).strip().lower()
            # Extract first word (beginner, intermediate, expert, etc.)
            words = level_text.split()
            if words:
                return words[0].strip('-')

        return "unknown"
