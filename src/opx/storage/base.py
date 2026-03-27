from __future__ import annotations

from abc import ABC, abstractmethod

from opx.models import BatchRunResult


class SignalStore(ABC):
    @abstractmethod
    def initialize(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def save_batch(self, batch: BatchRunResult) -> None:
        raise NotImplementedError

    @abstractmethod
    def load_batches(self, limit: int | None = None) -> list[BatchRunResult]:
        raise NotImplementedError
