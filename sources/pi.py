import asyncio
import logging
import os
from typing import Any

from registry import Registry
from sources import Source

logger = logging.getLogger(__name__)

PI_NAME = os.environ.get("PI_NAME", "Raspberry Pi")
PI_SOURCE_ID = os.environ.get("PI_SOURCE_ID", "system.pi")

POLL_INTERVAL_SEC = 10
THERMAL_PATH = "/sys/class/thermal/thermal_zone0/temp"


def _cpu_temp_c() -> float | None:
    """CPU temperature in °C, or None if the thermal zone isn't readable."""
    try:
        with open(THERMAL_PATH) as f:
            return round(int(f.read().strip()) / 1000, 1)
    except (OSError, ValueError):
        return None


def _mem_used_pct() -> float | None:
    """Used memory as a percentage, from /proc/meminfo (host, in the container)."""
    try:
        info: dict[str, int] = {}
        with open("/proc/meminfo") as f:
            for line in f:
                key, _, rest = line.partition(":")
                info[key] = int(rest.split()[0])  # kB
        total = info.get("MemTotal")
        avail = info.get("MemAvailable")
        if not total or avail is None:
            return None
        return round((total - avail) / total * 100, 1)
    except (OSError, ValueError, IndexError):
        return None


def _uptime_sec() -> float | None:
    try:
        with open("/proc/uptime") as f:
            return round(float(f.read().split()[0]))
    except (OSError, ValueError, IndexError):
        return None


class PiStatusSource(Source):
    """Publishes host vitals for the Raspberry Pi the monitor runs on:
    CPU temperature, load average, memory and uptime. Reads from /sys and
    /proc, which are visible to the container thanks to privileged + host
    networking.
    """

    async def run(self, registry: Registry) -> None:
        cores = os.cpu_count() or 1
        while True:
            try:
                load_1, load_5, load_15 = os.getloadavg()
                data: dict[str, Any] = {
                    "cpu_temp_c": _cpu_temp_c(),
                    "load_1": round(load_1, 2),
                    "load_5": round(load_5, 2),
                    "load_15": round(load_15, 2),
                    "load_pct": round(load_1 / cores * 100, 1),
                    "cpu_count": cores,
                    "mem_used_pct": _mem_used_pct(),
                    "uptime_sec": _uptime_sec(),
                }
                registry.publish(
                    PI_SOURCE_ID,
                    name=PI_NAME,
                    type="PiStatus",
                    data=data,
                )
            except Exception as e:
                logger.error(f"Pi status poll failed: {e}")

            await asyncio.sleep(POLL_INTERVAL_SEC)
