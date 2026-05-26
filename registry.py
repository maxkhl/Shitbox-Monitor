from datetime import datetime
from threading import Lock
from typing import Any


class Registry:
    """Thread-safe store of the latest snapshot from each data source."""

    def __init__(self) -> None:
        self._data: dict[str, dict[str, Any]] = {}
        self._lock = Lock()

    def publish(
        self,
        source_id: str,
        *,
        name: str,
        type: str,
        data: dict[str, Any],
    ) -> None:
        with self._lock:
            self._data[source_id] = {
                "name": name,
                "type": type,
                "data": data,
                "updated_at": datetime.now().isoformat(),
            }

    def snapshot(self) -> dict[str, dict[str, Any]]:
        with self._lock:
            return dict(self._data)
