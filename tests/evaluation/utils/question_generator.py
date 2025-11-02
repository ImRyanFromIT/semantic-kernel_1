"""
Question generator using LLM with persona context.

Generates evaluation questions by calling LLM with persona prompts
and SRM information, using retry logic for rate limiting.
"""

import re
import asyncio
import logging
from typing import List, Dict
from semantic_kernel import Kernel
from semantic_kernel.contents import ChatHistory
from semantic_kernel.connectors.ai.chat_completion_client_base import ChatCompletionClientBase
from semantic_kernel.connectors.ai.prompt_execution_settings import PromptExecutionSettings

from tests.evaluation.utils.persona_loader import Persona


class QuestionGenerator:
    """Generates questions using LLM with persona context."""

    QUESTION_TYPES = ["direct", "problem", "vague"]

    def __init__(self, kernel: Kernel, max_retries: int = 3, retry_delay: int = 2):
        """
        Initialize question generator.

        Args:
            kernel: Semantic Kernel instance
            max_retries: Maximum retry attempts for LLM calls
            retry_delay: Initial delay between retries (seconds)
        """
        self.kernel = kernel
        self.chat_service = kernel.get_service(type=ChatCompletionClientBase)
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.logger = logging.getLogger(__name__)

    async def generate_questions(
        self,
        persona: Persona,
        srm_data: Dict[str, str]
    ) -> List[Dict[str, str]]:
        """
        Generate 3 questions for an SRM from persona perspective.

        Args:
            persona: Persona object with context
            srm_data: SRM information dict

        Returns:
            List of 3 question dicts with query, query_type

        Raises:
            Exception: If generation fails after all retries
        """
        prompt = self._build_prompt(persona, srm_data)

        # Retry logic with exponential backoff
        for attempt in range(self.max_retries):
            try:
                # Create chat history with system message
                chat_history = ChatHistory()
                chat_history.add_user_message(prompt)

                # Create execution settings
                settings = PromptExecutionSettings(
                    service_id="chat",
                    max_tokens=500,
                    temperature=0.7
                )

                # Call LLM
                response = await self.chat_service.get_chat_message_content(
                    chat_history=chat_history,
                    settings=settings
                )

                # Parse questions
                question_texts = self._parse_questions(response.content)

                if len(question_texts) != 3:
                    raise ValueError(f"Expected 3 questions, got {len(question_texts)}")

                # Build result with metadata
                questions = []
                for i, (question_text, question_type) in enumerate(zip(question_texts, self.QUESTION_TYPES)):
                    questions.append({
                        'query': question_text,
                        'query_type': question_type
                    })

                return questions

            except Exception as e:
                self.logger.warning(f"Attempt {attempt + 1} failed: {e}")

                if attempt < self.max_retries - 1:
                    delay = self.retry_delay * (2 ** attempt)
                    self.logger.info(f"Retrying in {delay}s...")
                    await asyncio.sleep(delay)
                else:
                    self.logger.error(f"All retries exhausted for {srm_data['SRM_ID']}")
                    raise

    def _build_prompt(self, persona: Persona, srm_data: Dict[str, str]) -> str:
        """
        Build LLM prompt with persona and SRM context.

        Args:
            persona: Persona with full context
            srm_data: SRM information

        Returns:
            Formatted prompt string
        """
        prompt = f"""{persona.content}

---

SERVICE INFORMATION:
Name: {srm_data['Name']}
ID: {srm_data['SRM_ID']}
Description: {srm_data['Description']}
Technologies: {srm_data.get('TechnologiesTeamWorksWith', 'N/A')}

---

Generate 3 questions from your perspective as this persona:

1. DIRECT REQUEST: Ask for this service clearly (though phrased how you would naturally ask)

2. PROBLEM-BASED: Describe a problem or situation that this service would solve

3. VAGUE/UNCLEAR: Ask about this in an ambiguous or unclear way that might need clarification

IMPORTANT:
- Stay in character for all questions
- Use your natural language and terminology from the persona description
- Each question should be a single-turn query (not a conversation)
- Return only the 3 questions, numbered 1-3, one per line
- Do not include any other text or explanation
"""
        return prompt

    def _parse_questions(self, response: str) -> List[str]:
        """
        Parse numbered questions from LLM response.

        Args:
            response: Raw LLM response text

        Returns:
            List of question strings
        """
        questions = []

        # Match lines starting with "1.", "2.", "3."
        pattern = r'^\s*(\d+)\.\s*(.+)$'

        for line in response.strip().split('\n'):
            match = re.match(pattern, line.strip())
            if match:
                question_num = int(match.group(1))
                question_text = match.group(2).strip()

                if 1 <= question_num <= 3:
                    questions.append(question_text)

        return questions
