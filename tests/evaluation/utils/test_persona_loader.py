"""Tests for persona loader."""

import pytest
from pathlib import Path
from tests.evaluation.utils.persona_loader import PersonaLoader, Persona


def test_discover_personas(tmp_path):
    """Test discovering persona files."""
    # Create test persona files
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()

    persona1 = prompts_dir / "test_user.md"
    persona1.write_text("# Test User\n\n## Technical Level\nBeginner")

    persona2 = prompts_dir / "expert.md"
    persona2.write_text("# Expert\n\n## Technical Level\nExpert")

    loader = PersonaLoader(prompts_dir)
    personas = loader.discover_personas()

    assert len(personas) == 2
    assert any(p.id == "test_user" for p in personas)
    assert any(p.id == "expert" for p in personas)


def test_load_persona_content():
    """Test loading persona with metadata."""
    loader = PersonaLoader(Path("tests/evaluation/prompts"))
    personas = loader.discover_personas()

    # Should have at least one persona
    assert len(personas) > 0

    # Check first persona has required fields
    persona = personas[0]
    assert persona.id
    assert persona.name
    assert persona.content
    assert len(persona.content) > 50  # Has actual content


def test_parse_persona_name():
    """Test extracting persona name from H1 header."""
    content = "# Lost End User\n\nSome content"
    loader = PersonaLoader(Path("."))
    name = loader._parse_persona_name(content)
    assert name == "Lost End User"


def test_parse_technical_level():
    """Test extracting technical level."""
    content = """# User

## Technical Level
Beginner - basic skills

## Other Section
Content
"""
    loader = PersonaLoader(Path("."))
    level = loader._parse_technical_level(content)
    assert level == "beginner"


def test_exclude_readme_files(tmp_path):
    """Test that README.md files are excluded from persona discovery."""
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()

    # Create a regular persona file
    persona1 = prompts_dir / "developer.md"
    persona1.write_text("# Developer\n\n## Technical Level\nExpert")

    # Create README files with different casings
    readme1 = prompts_dir / "README.md"
    readme1.write_text("# Documentation\n\nThis is a readme file")

    readme2 = prompts_dir / "readme.md"
    readme2.write_text("# Readme\n\nAnother readme")

    readme3 = prompts_dir / "ReadMe.md"
    readme3.write_text("# ReadMe\n\nYet another readme")

    loader = PersonaLoader(prompts_dir)
    personas = loader.discover_personas()

    # Should only find the developer persona, not any README files
    assert len(personas) == 1
    assert personas[0].id == "developer"
    assert personas[0].name == "Developer"
