"""
Azure OpenAI embedding service for vector search.

Provides embedding generation for SRM documents using Azure OpenAI's text-embedding models.
"""

import asyncio
import os
from typing import List, Optional
from dataclasses import dataclass

from azure.identity import AzureCliCredential
from semantic_kernel.connectors.ai.open_ai import AzureTextEmbedding
from dotenv import load_dotenv


@dataclass
class EmbeddingConfig:
    """Configuration for Azure OpenAI embedding service."""
    endpoint: str
    deployment_name: str
    api_key: Optional[str] = None
    api_version: str = "2024-05-01-preview"
    embedding_dimensions: int = 1536  # text-embedding-3-small default


class AzureEmbeddingService:
    """
    Service for generating embeddings using Azure OpenAI.

    Uses the same Azure OpenAI configuration as the main chatbot kernel,
    supporting both API key and Azure CLI credential authentication.
    """

    def __init__(self, config: Optional[EmbeddingConfig] = None):
        """
        Initialize the embedding service.

        Args:
            config: Optional embedding configuration. If not provided,
                   loads from environment variables.
        """
        if config is None:
            config = self._load_config_from_env()

        self.config = config
        self._service = self._create_embedding_service()

    @staticmethod
    def _load_config_from_env() -> EmbeddingConfig:
        """Load embedding configuration from environment variables."""
        load_dotenv()

        endpoint = os.getenv('AZURE_OPENAI_ENDPOINT')
        if not endpoint:
            raise ValueError(
                "AZURE_OPENAI_ENDPOINT environment variable is required. "
                "See .env.example for configuration details."
            )

        deployment_name = os.getenv(
            'AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME',
            'text-embedding-3-small'
        )
        api_key = os.getenv('AZURE_OPENAI_API_KEY')
        api_version = os.getenv('AZURE_OPENAI_API_VERSION', '2024-05-01-preview')

        return EmbeddingConfig(
            endpoint=endpoint,
            deployment_name=deployment_name,
            api_key=api_key,
            api_version=api_version,
        )

    def _create_embedding_service(self) -> AzureTextEmbedding:
        """Create the Azure Text Embedding service."""
        if self.config.api_key:
            # Use API key authentication
            return AzureTextEmbedding(
                service_id="embedding",
                deployment_name=self.config.deployment_name,
                endpoint=self.config.endpoint,
                api_key=self.config.api_key,
                api_version=self.config.api_version,
            )
        else:
            # Use Azure CLI credential
            credential = AzureCliCredential()
            return AzureTextEmbedding(
                service_id="embedding",
                deployment_name=self.config.deployment_name,
                endpoint=self.config.endpoint,
                credential=credential,
                api_version=self.config.api_version,
            )

    async def generate_embedding(self, text: str, max_retries: int = 3) -> List[float]:
        """
        Generate embedding for a single text with retry logic.

        Args:
            text: Input text to embed
            max_retries: Number of retry attempts (default: 3)

        Returns:
            List of floats representing the embedding vector

        Raises:
            ValueError: If text is empty
            Exception: If API call fails after all retries
        """
        if not text or not text.strip():
            raise ValueError("Cannot generate embedding for empty text")

        # Try multiple times with exponential backoff
        last_error = None
        for attempt in range(max_retries):
            try:
                # Generate embedding using the service
                embeddings = await self._service.generate_embeddings([text])

                # Return the first (and only) embedding
                return embeddings[0].tolist() if hasattr(embeddings[0], 'tolist') else list(embeddings[0])

            except Exception as e:
                last_error = e
                if attempt < max_retries - 1:
                    # Wait before retry (exponential backoff)
                    wait_time = 0.5 * (2 ** attempt)  # 0.5s, 1s, 2s
                    await asyncio.sleep(wait_time)
                else:
                    # Final attempt failed
                    raise last_error

    async def generate_embeddings_batch(
        self,
        texts: List[str],
        batch_size: int = 16,
        show_progress: bool = True
    ) -> List[List[float]]:
        """
        Generate embeddings for multiple texts with batching and rate limiting.

        Args:
            texts: List of texts to embed
            batch_size: Number of texts to process in each batch
            show_progress: Whether to print progress updates

        Returns:
            List of embedding vectors

        Raises:
            ValueError: If any text is empty
        """
        if not texts:
            return []

        # Validate inputs
        for i, text in enumerate(texts):
            if not text or not text.strip():
                raise ValueError(f"Text at index {i} is empty")

        embeddings = []
        total_batches = (len(texts) + batch_size - 1) // batch_size

        for batch_idx in range(0, len(texts), batch_size):
            batch = texts[batch_idx:batch_idx + batch_size]

            if show_progress:
                current_batch = batch_idx // batch_size + 1
                print(f"[*] Generating embeddings: batch {current_batch}/{total_batches} "
                      f"({len(batch)} texts)...")

            # Generate embeddings for this batch
            try:
                batch_embeddings = await self._service.generate_embeddings(batch)

                # Convert to list of lists
                for emb in batch_embeddings:
                    embedding_list = emb.tolist() if hasattr(emb, 'tolist') else list(emb)
                    embeddings.append(embedding_list)

                # Small delay between batches to avoid rate limiting
                if batch_idx + batch_size < len(texts):
                    await asyncio.sleep(0.1)

            except Exception as e:
                print(f"[!] Error generating embeddings for batch {current_batch}: {e}")
                raise

        if show_progress:
            print(f"[✓] Generated {len(embeddings)} embeddings")

        return embeddings

    def generate_embedding_sync(self, text: str) -> List[float]:
        """
        Synchronous wrapper for generate_embedding.

        Args:
            text: Input text to embed

        Returns:
            Embedding vector
        """
        return asyncio.run(self.generate_embedding(text))

    def generate_embeddings_batch_sync(
        self,
        texts: List[str],
        batch_size: int = 16,
        show_progress: bool = True
    ) -> List[List[float]]:
        """
        Synchronous wrapper for generate_embeddings_batch.

        Args:
            texts: List of texts to embed
            batch_size: Number of texts per batch
            show_progress: Whether to show progress

        Returns:
            List of embedding vectors
        """
        return asyncio.run(self.generate_embeddings_batch(texts, batch_size, show_progress))


def create_embedding_text(name: str, description: str, technologies: str = "") -> str:
    """
    Create a combined text representation for embedding generation.

    Combines SRM name, description, and technologies into a single text
    optimized for semantic search.

    Args:
        name: SRM name/title
        description: SRM description
        technologies: Technologies the team works with

    Returns:
        Combined text suitable for embedding
    """
    parts = []

    if name:
        parts.append(f"Service: {name}")

    if description:
        parts.append(f"Description: {description}")

    if technologies:
        parts.append(f"Technologies: {technologies}")

    return " | ".join(parts)
