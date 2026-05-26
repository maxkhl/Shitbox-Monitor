from abc import ABC, abstractmethod

from registry import Registry


class Source(ABC):
    """A data source that publishes its latest snapshot into the registry."""

    @abstractmethod
    async def run(self, registry: Registry) -> None:
        """Start the source. Should run until cancelled."""
