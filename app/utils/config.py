import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict

from pydantic import BaseModel, Field, HttpUrl, ValidationError


class OpenAIDeployments(BaseModel):
    chat: str = Field(..., description="Deployment name for chat/completions model")
    embeddings: str = Field(..., description="Deployment name for embeddings model")


class AzureOpenAIConfig(BaseModel):
    endpoint: HttpUrl
    api_key: str
    deployments: OpenAIDeployments


class AzureSearchConfig(BaseModel):
    endpoint: HttpUrl
    api_key: str
    index_name: str


class IngestionConfig(BaseModel):
    data_dir: str = "./data"
    ppt_team_mapping: Dict[str, str] = Field(default_factory=dict)


class AppConfig(BaseModel):
    azure_openai: AzureOpenAIConfig
    azure_search: AzureSearchConfig
    ingestion: IngestionConfig


def _load_config_file() -> Dict[str, Any]:
    """Read the config.json next to project root `semantic-kernel_poc/`.

    Returns raw dictionary for further Pydantic validation.
    """
    # Resolve relative to this file: semantic-kernel_poc/app/utils/config.py
    root = Path(__file__).resolve().parents[2]
    cfg_path = root / "config.json"
    if not cfg_path.exists():
        raise FileNotFoundError(f"config.json not found at {cfg_path}")
    with cfg_path.open("r", encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def get_config() -> AppConfig:
    """Load and validate configuration once per process."""
    try:
        raw = _load_config_file()
        return AppConfig.model_validate(raw)
    except (OSError, ValidationError) as exc:
        logging.getLogger(__name__).exception("Failed to load configuration")
        raise


