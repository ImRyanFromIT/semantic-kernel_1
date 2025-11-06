"""Tests for question generator."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from tests.evaluation.utils.question_generator import QuestionGenerator
from tests.evaluation.utils.persona_loader import Persona


@pytest.fixture
def mock_kernel():
    """Create mock kernel with chat service."""
    kernel = MagicMock()
    chat_service = AsyncMock()
    kernel.get_service.return_value = chat_service
    return kernel


@pytest.fixture
def sample_persona():
    """Create sample persona."""
    return Persona(
        id="test_user",
        name="Test User",
        content="# Test User\n\nA test persona",
        technical_level="beginner"
    )


@pytest.fixture
def sample_srm():
    """Create sample SRM data."""
    return {
        'SRM_ID': 'SRM-001',
        'Name': 'Test Service',
        'Description': 'A test service for testing',
        'TechnologiesTeamWorksWith': 'Python, Azure'
    }


@pytest.mark.asyncio
async def test_generate_questions_success(mock_kernel, sample_persona, sample_srm):
    """Test successful question generation."""
    # Mock LLM response
    mock_response = """1. I need help with the test service
2. My test service isn't working right
3. Can you help me with something?"""

    chat_service = mock_kernel.get_service.return_value
    chat_service.get_chat_message_content = AsyncMock(return_value=MagicMock(content=mock_response))

    generator = QuestionGenerator(mock_kernel)
    questions = await generator.generate_questions(sample_persona, sample_srm)

    assert len(questions) == 3
    assert questions[0]['query'] == "I need help with the test service"
    assert questions[0]['query_type'] == "direct"
    assert questions[1]['query_type'] == "problem"
    assert questions[2]['query_type'] == "vague"


@pytest.mark.asyncio
async def test_generate_questions_with_retry(mock_kernel, sample_persona, sample_srm):
    """Test retry logic on API failure."""
    chat_service = mock_kernel.get_service.return_value

    # First call fails, second succeeds
    chat_service.get_chat_message_content = AsyncMock(
        side_effect=[
            Exception("Rate limit"),
            MagicMock(content="1. Question 1\n2. Question 2\n3. Question 3")
        ]
    )

    with patch('tests.evaluation.utils.question_generator.asyncio.sleep'):
        generator = QuestionGenerator(mock_kernel, max_retries=2, retry_delay=1)
        questions = await generator.generate_questions(sample_persona, sample_srm)

        assert len(questions) == 3
        assert chat_service.get_chat_message_content.call_count == 2


@pytest.mark.asyncio
async def test_parse_questions():
    """Test parsing numbered questions from LLM response."""
    response = """1. First question here
2. Second question here
3. Third question here"""

    generator = QuestionGenerator(MagicMock())
    questions = generator._parse_questions(response)

    assert len(questions) == 3
    assert questions[0] == "First question here"
    assert questions[1] == "Second question here"
    assert questions[2] == "Third question here"


@pytest.mark.asyncio
async def test_parse_questions_with_extra_content():
    """Test parsing when LLM includes extra text."""
    response = """Here are the questions:

1. First question
2. Second question
3. Third question

I hope these help!"""

    generator = QuestionGenerator(MagicMock())
    questions = generator._parse_questions(response)

    assert len(questions) == 3


def test_build_prompt(sample_persona, sample_srm):
    """Test prompt construction."""
    generator = QuestionGenerator(MagicMock())
    prompt = generator._build_prompt(sample_persona, sample_srm)

    # Check all required elements are in prompt
    assert sample_persona.content in prompt
    assert sample_srm['Name'] in prompt
    assert sample_srm['SRM_ID'] in prompt
    assert sample_srm['Description'] in prompt
    assert "DIRECT REQUEST" in prompt
    assert "PROBLEM-BASED" in prompt
    assert "VAGUE/UNCLEAR" in prompt
