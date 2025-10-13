'''
Kernel configuration and initialization.
'''

import os
from dotenv import load_dotenv

from azure.identity import AzureCliCredential
from semantic_kernel import Kernel
from semantic_kernel.connectors.ai.open_ai import (
    AzureChatCompletion,
    AzureTextEmbedding,
)


def create_kernel() -> Kernel:
    '''
    Create and configure a Semantic Kernel instance.
    
    Loads configuration from .env file and sets up:
    - Azure OpenAI chat completion service
    - Azure OpenAI text embedding service
    
    Returns:
        Configured Kernel instance
    '''
    # Load environment variables
    load_dotenv()
    
    # Get configuration from environment
    endpoint = os.getenv('AZURE_OPENAI_ENDPOINT')
    api_key = os.getenv('AZURE_OPENAI_API_KEY')
    chat_deployment = os.getenv('AZURE_OPENAI_CHAT_DEPLOYMENT_NAME', 'gpt-5-chat')
    embedding_deployment = os.getenv('AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME', 'text-embedding-3-small')
    api_version = os.getenv('AZURE_OPENAI_API_VERSION', '2024-05-01-preview')
    
    # Initialize kernel
    kernel = Kernel()
    
    # Service IDs
    chat_service_id = "chat"
    embedding_service_id = "embedding"
    
    # Configure authentication
    if api_key:
        # Use API key authentication
        chat_service = AzureChatCompletion(
            service_id=chat_service_id,
            deployment_name=chat_deployment,
            endpoint=endpoint,
            api_key=api_key,
            api_version=api_version,
        )
        embedding_service = AzureTextEmbedding(
            service_id=embedding_service_id,
            deployment_name=embedding_deployment,
            endpoint=endpoint,
            api_key=api_key,
            api_version=api_version,
        )
    else:
        # Use Azure CLI credential
        credential = AzureCliCredential()
        chat_service = AzureChatCompletion(
            service_id=chat_service_id,
            deployment_name=chat_deployment,
            endpoint=endpoint,
            credential=credential,
            api_version=api_version,
        )
        embedding_service = AzureTextEmbedding(
            service_id=embedding_service_id,
            deployment_name=embedding_deployment,
            endpoint=endpoint,
            credential=credential,
            api_version=api_version,
        )
    
    # Add services to kernel
    kernel.add_service(chat_service)
    kernel.add_service(embedding_service)
    
    # Load all prompt-based plugins
    try:
        from src.utils.plugin_loader import load_all_plugins
        load_all_plugins(kernel)
    except Exception as e:
        print(f"[!] Warning: Failed to load plugins: {e}")
        print("[*] Continuing without plugins...")
    
    return kernel

