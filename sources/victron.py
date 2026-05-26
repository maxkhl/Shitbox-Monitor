import asyncio
import json
import logging
import os
import threading
from typing import Any

from victron_ble.devices import detect_device_type
from victron_ble.scanner import Scanner

from registry import Registry
from sources import Source

logger = logging.getLogger(__name__)


def _load_devices() -> dict[str, tuple[str, str]]:
    """Parse VICTRON_DEVICES env var.

    Format: JSON array of objects, each with 'mac', 'key', and 'name'.
    Example:
        VICTRON_DEVICES='[{"mac":"aa:bb:cc:dd:ee:ff","key":"...","name":"SmartShunt"}]'
    """
    raw = os.environ.get("VICTRON_DEVICES", "").strip()
    if not raw:
        return {}
    try:
        items = json.loads(raw)
        return {
            d["mac"].lower(): (d["key"], d.get("name", d["mac"]))
            for d in items
        }
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        logger.error(f"VICTRON_DEVICES parse failed: {e}")
        return {}


DEVICES: dict[str, tuple[str, str]] = _load_devices()


def _extract(parsed) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for name in dir(parsed):
        if not name.startswith("get_"):
            continue
        try:
            val = getattr(parsed, name)()
            result[name[4:]] = val.name if hasattr(val, "name") else val
        except Exception:
            pass
    return result


class _VictronScanner(Scanner):
    def __init__(self, device_keys: dict[str, str], registry: Registry) -> None:
        super().__init__(device_keys)
        self._registry = registry

    def callback(self, ble_device, data, advertisement) -> None:
        try:
            mac = ble_device.address.lower()
            if mac not in DEVICES:
                return
            device_class = detect_device_type(data)
            if not device_class:
                return
            key, name = DEVICES[mac]
            parsed = device_class(key).parse(data)
            self._registry.publish(
                f"victron.{name.lower()}",
                name=name,
                type=device_class.__name__,
                data=_extract(parsed),
            )
        except Exception as e:
            logger.error(f"Parse error ({ble_device.address}): {e}", exc_info=True)


class VictronBleSource(Source):
    """Bridges Victron BLE advertisements into the registry.

    Runs in a dedicated thread with its own event loop; victron_ble.Scanner
    is built on bleak and is kept isolated from FastAPI's loop.
    """

    async def run(self, registry: Registry) -> None:
        if not DEVICES:
            logger.warning("VICTRON_DEVICES not configured; Victron source disabled")
            return

        def _thread() -> None:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                device_keys = {mac: key for mac, (key, _) in DEVICES.items()}
                scanner = _VictronScanner(device_keys, registry)
                loop.run_until_complete(_serve(scanner))
            except Exception as e:
                logger.error(f"Victron scanner crashed: {e}", exc_info=True)

        threading.Thread(target=_thread, daemon=True, name="victron-ble").start()
        await asyncio.Event().wait()


async def _serve(scanner: _VictronScanner) -> None:
    await scanner.start()
    await asyncio.Event().wait()
