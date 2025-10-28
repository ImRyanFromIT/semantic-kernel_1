"""
Configuration model for the SRM Archivist Agent.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class GraphApiConfig:
    """Microsoft Graph API configuration."""
    tenant_id: str
    client_id: str
    client_secret: str
    mailbox: str


@dataclass
class AzureSearchConfig:
    """Azure AI Search configuration."""
    endpoint: str
    index_name: str
    api_key: str


@dataclass
class LlmConfig:
    """LLM configuration."""
    model: str = "gpt-4"
    temperature: float = 0.3
    max_tokens: int = 1500


@dataclass
class AgentConfig:
    """
    Complete agent configuration loaded from agent_plan.yaml and environment.
    """
    
    # Agent identity
    agent_name: str = "SRM_Archivist_Agent"
    description: str = "Monitors email inbox for SRM change requests and updates Azure AI Search index"
    
    # File paths
    state_file: str = "agent_state.jsonl"
    log_file: str = "agent_actions.log"
    
    # Update behavior
    mock_updates: bool = True  # If True, mock updates; if False, actually update index
    
    # Timing configuration
    email_scan_interval_seconds: int = 30
    stale_item_hours: int = 48
    clarification_wait_hours: int = 48
    email_history_window_days: int = 7
    
    # Processing thresholds
    mass_email_threshold: int = 20
    confidence_threshold_for_classification: int = 70
    
    # Retry configuration
    max_retries_api_calls: int = 3
    retry_delay_seconds: int = 300
    
    # Email configuration
    support_team_email: str = ""
    
    # Service configurations
    graph_api: Optional[GraphApiConfig] = None
    azure_search: Optional[AzureSearchConfig] = None
    llm_config: Optional[LlmConfig] = None
    
    @classmethod
    def from_yaml_and_env(cls, yaml_data: dict, env_vars: dict) -> 'AgentConfig':
        """
        Create configuration from YAML data and environment variables.
        
        Args:
            yaml_data: Parsed YAML configuration
            env_vars: Environment variables dictionary
            
        Returns:
            AgentConfig instance
        """
        config_data = yaml_data.get('configuration', {})
        
        # Create service configurations
        graph_config = None
        if 'graph_api' in config_data:
            graph_data = config_data['graph_api']
            graph_config = GraphApiConfig(
                tenant_id=env_vars.get('TENANT_ID', ''),
                client_id=env_vars.get('CLIENT_ID', ''),
                client_secret=env_vars.get('CLIENT_SECRET', ''),
                mailbox=env_vars.get('MAILBOX_EMAIL', ''),
            )
        
        azure_search_config = None
        if 'azure_search' in config_data:
            azure_search_config = AzureSearchConfig(
                endpoint=env_vars.get('AZURE_AI_SEARCH_ENDPOINT', ''),
                index_name=env_vars.get('AZURE_AI_SEARCH_INDEX_NAME', ''),
                api_key=env_vars.get('AZURE_AI_SEARCH_API_KEY', ''),
            )
        
        llm_config = None
        if 'llm_config' in config_data:
            llm_data = config_data['llm_config']
            llm_config = LlmConfig(
                model=llm_data.get('model', 'gpt-4'),
                temperature=llm_data.get('temperature', 0.3),
                max_tokens=llm_data.get('max_tokens', 1500),
            )
        
        return cls(
            agent_name=yaml_data.get('agent_name', 'SRM_Archivist_Agent'),
            description=yaml_data.get('description', ''),
            state_file=yaml_data.get('state_file', 'agent_state.jsonl'),
            log_file=yaml_data.get('log_file', 'agent_actions.log'),
            mock_updates=yaml_data.get('mock_updates', True),
            email_scan_interval_seconds=config_data.get('email_scan_interval_seconds', 30),
            stale_item_hours=config_data.get('stale_item_hours', 48),
            clarification_wait_hours=config_data.get('clarification_wait_hours', 48),
            email_history_window_days=config_data.get('email_history_window_days', 7),
            mass_email_threshold=config_data.get('mass_email_threshold', 20),
            confidence_threshold_for_classification=config_data.get('confidence_threshold_for_classification', 70),
            max_retries_api_calls=config_data.get('max_retries_api_calls', 3),
            retry_delay_seconds=config_data.get('retry_delay_seconds', 300),
            support_team_email=env_vars.get('SUPPORT_TEAM_EMAIL', ''),
            graph_api=graph_config,
            azure_search=azure_search_config,
            llm_config=llm_config,
        )
