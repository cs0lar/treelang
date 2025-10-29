from abc import ABC, abstractmethod
from typing import List

from pydantic import BaseModel


class ChatMessage(BaseModel):
    role: str
    content: str


class Memory(ABC):
    """Abstract base class for memory implementations."""

    @abstractmethod
    def add(self, messages: List[ChatMessage]) -> None:
        """Add chat messages to the memory."""
        pass

    @abstractmethod
    def get(self) -> List[ChatMessage]:
        """Retrieve items from memory based on a query."""
        pass

    @abstractmethod
    def clear(self) -> None:
        """Clear all items from the memory."""
        pass
