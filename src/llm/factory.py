"""
LLM Factory Module.
Instantiates LLM provider adapters based on environment configuration.
"""

import logging
import os
from typing import Optional

from src.llm.base import BaseLLMClient
from src.llm.groq_client import GroqClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("LLMFactory")


class LLMFactory:
    """Factory to instantiate the appropriate LLM client."""

    @staticmethod
    def get_client(provider: Optional[str] = None) -> BaseLLMClient:
        active_provider = (provider or os.getenv("LLM_PROVIDER", "groq")).lower()

        if active_provider == "groq":
            logger.info("Instantiating GroqClient...")
            return GroqClient()
        else:
            logger.info(f"Provider '{active_provider}' requested; defaulting to GroqClient wrapper.")
            return GroqClient()

