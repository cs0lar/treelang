from abc import ABC, abstractmethod
from typing import List

from pydantic import BaseModel


class ChatMessage(BaseModel):
    role: str
    content: str


class Memory(ABC):
    """Abstract base class for memory implementations."""

    @abstractmethod
    async def add(self, messages: List[ChatMessage]) -> None:
        """Asynchronously add chat messages to the memory."""
        pass

    @abstractmethod
    async def get(self) -> List[ChatMessage]:
        """Asynchronously retrieve items from memory based on a query."""
        pass

    @abstractmethod
    async def clear(self) -> None:
        """Asynchronously clear all items from the memory."""
        pass
