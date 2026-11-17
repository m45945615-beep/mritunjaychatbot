"""
Abstract Base Interface for LLM Providers.
"""

from abc import ABC, abstractmethod


class BaseLLMClient(ABC):
    """Abstract base class for all LLM provider clients."""

    @abstractmethod
    def generate(self, prompt: str) -> str:
        """Generates a text completion for the provided prompt."""
        pass

