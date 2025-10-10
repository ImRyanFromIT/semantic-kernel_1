from __future__ import annotations

from typing import Any

from semantic_kernel import Kernel
from semantic_kernel.connectors.ai.open_ai.services.azure_open_ai import AzureOpenAIChatCompletion, AzureOpenAITextEmbedding

from ..utils.config import get_config


def build_kernel() -> Kernel:
    cfg = get_config()
    kernel = Kernel()
    chat = AzureOpenAIChatCompletion(
        service_id="chat",
        deployment_name=cfg.azure_openai.deployments.chat,
        endpoint=str(cfg.azure_openai.endpoint),
        api_key=cfg.azure_openai.api_key,
    )
    embeddings = AzureOpenAITextEmbedding(
        service_id="embeddings",
        deployment_name=cfg.azure_openai.deployments.embeddings,
        endpoint=str(cfg.azure_openai.endpoint),
        api_key=cfg.azure_openai.api_key,
    )
    kernel.add_service(chat)
    kernel.add_service(embeddings)
    return kernel


