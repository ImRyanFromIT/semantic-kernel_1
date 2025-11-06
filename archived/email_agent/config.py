"""
Configuration management for the SRM Archivist Agent.
"""

import os
import yaml
from typing import Dict, Any
from dotenv import load_dotenv

from src.models.agent_config import AgentConfig


def load_config(config_file: str = "agent_plan.yaml") -> AgentConfig:
    """
    Load agent configuration from YAML file and environment variables.
    
    Args:
        config_file: Path to the YAML configuration file
        
    Returns:
        AgentConfig instance with loaded configuration
        
    Raises:
        FileNotFoundError: If config file doesn't exist
        yaml.YAMLError: If YAML parsing fails
    """
    # Load environment variables from .env file
    load_dotenv()
    
    # Load YAML configuration
    if not os.path.exists(config_file):
        raise FileNotFoundError(f"Configuration file not found: {config_file}")
    
    with open(config_file, 'r', encoding='utf-8') as f:
        yaml_data = yaml.safe_load(f)
    
    # Get environment variables
    env_vars = dict(os.environ)
    
    # Create and return configuration
    return AgentConfig.from_yaml_and_env(yaml_data, env_vars)


# Alias for backward compatibility
load_agent_config = load_config


def validate_config(config: AgentConfig) -> list[str]:
    """
    Validate agent configuration and return list of issues.
    
    Args:
        config: AgentConfig to validate
        
    Returns:
        List of validation error messages (empty if valid)
    """
    issues = []
    
    # Validate Graph API configuration
    if not config.graph_api:
        issues.append("Microsoft Graph API configuration is missing")
    else:
        if not config.graph_api.tenant_id:
            issues.append("TENANT_ID environment variable is required")
        if not config.graph_api.client_id:
            issues.append("CLIENT_ID environment variable is required")
        if not config.graph_api.client_secret:
            issues.append("CLIENT_SECRET environment variable is required")
        if not config.graph_api.mailbox:
            issues.append("MAILBOX_EMAIL environment variable is required")
    
    # Validate Azure Search configuration
    if not config.azure_search:
        issues.append("Azure AI Search configuration is missing")
    else:
        if not config.azure_search.endpoint:
            issues.append("AZURE_AI_SEARCH_ENDPOINT environment variable is required")
        if not config.azure_search.index_name:
            issues.append("AZURE_AI_SEARCH_INDEX_NAME environment variable is required")
        if not config.azure_search.api_key:
            issues.append("AZURE_AI_SEARCH_API_KEY environment variable is required")
    
    # Validate timing configuration
    if config.email_scan_interval_seconds < 10:
        issues.append("Email scan interval should be at least 10 seconds")
    if config.mass_email_threshold < 1:
        issues.append("Mass email threshold should be at least 1")
    if config.confidence_threshold_for_classification < 0 or config.confidence_threshold_for_classification > 100:
        issues.append("Confidence threshold should be between 0 and 100")
    
    return issues
