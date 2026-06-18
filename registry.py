from datetime import datetime
from threading import Lock
from typing import Any

_STALE_SECONDS = 60


class Registry:
    """Thread-safe store of the latest snapshot from each data source."""

    def __init__(self) -> None:
        self._data: dict[str, dict[str, Any]] = {}
        self._persistent: set[str] = set()
        self._lock = Lock()

    def declare(self, source_id: str, *, name: str, type: str) -> None:
        """Register a device that should appear in snapshots even before/after BLE is seen."""
        with self._lock:
            self._persistent.add(source_id)
            if source_id not in self._data:
                self._data[source_id] = {
                    "name": name,
                    "type": type,
                    "data": {},
                    "updated_at": None,
                }

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
        now = datetime.now()
        with self._lock:
            result = {}
            for k, v in self._data.items():
                entry = dict(v)
                if k in self._persistent:
                    updated = v.get("updated_at")
                    if updated:
                        age = (now - datetime.fromisoformat(updated)).total_seconds()
                        entry["offline"] = age > _STALE_SECONDS
                    else:
                        entry["offline"] = True
                result[k] = entry
            return result
