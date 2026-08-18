from abc import ABC, abstractmethod
from typing import Any


class DatabaseAdapter(ABC):
    @abstractmethod
    def connect(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def execute(self, query: str, params: dict[str, Any] | None = None) -> None:
        raise NotImplementedError

    @abstractmethod
    def close(self) -> None:
        raise NotImplementedError