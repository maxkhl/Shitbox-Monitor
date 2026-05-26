import asyncio
import logging
import os
from typing import Any

import httpx

from registry import Registry
from sources import Source

logger = logging.getLogger(__name__)

ROUTER_URL = os.environ.get("ROUTER_URL", "http://192.168.1.1")
ROUTER_USER = os.environ.get("ROUTER_USER", "admin")
ROUTER_PASSWORD = os.environ.get("ROUTER_PASSWORD")

POLL_INTERVAL_SEC = 10
REQUEST_TIMEOUT_SEC = 8


class TeltonikaSource(Source):
    """Polls a Teltonika router (RUTX11, RutOS 7.x) for GPS + mobile/LTE status."""

    async def run(self, registry: Registry) -> None:
        if not ROUTER_PASSWORD:
            logger.warning("ROUTER_PASSWORD not set; Teltonika source disabled")
            return

        async with httpx.AsyncClient(
            base_url=ROUTER_URL,
            verify=False,
            timeout=REQUEST_TIMEOUT_SEC,
        ) as client:
            token: str | None = None
            while True:
                try:
                    if token is None:
                        token = await self._login(client)
                    headers = {"Authorization": f"Bearer {token}"}
                    await self._poll_once(client, headers, registry)
                except httpx.HTTPStatusError as e:
                    if e.response.status_code in (401, 403):
                        logger.info("Router token rejected, will re-login next cycle")
                        token = None
                    else:
                        logger.error(f"Router HTTP error: {e}")
                except Exception as e:
                    logger.error(f"Router poll failed: {e}")

                await asyncio.sleep(POLL_INTERVAL_SEC)

    async def _login(self, client: httpx.AsyncClient) -> str:
        r = await client.post(
            "/api/login",
            json={"username": ROUTER_USER, "password": ROUTER_PASSWORD},
        )
        r.raise_for_status()
        body = r.json()
        return body["data"]["token"]

    async def _poll_once(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        registry: Registry,
    ) -> None:
        gps = await self._get(client, "/api/gps/position/status", headers)
        if gps:
            registry.publish("router.gps", name="GPS", type="GPS", data=gps)

        mobile = await self._get(client, "/api/modems/status", headers)
        if isinstance(mobile, list) and mobile:
            mobile = mobile[0]
        if mobile:
            registry.publish("router.mobile", name="Mobile", type="Mobile", data=mobile)

    async def _get(
        self,
        client: httpx.AsyncClient,
        path: str,
        headers: dict[str, str],
    ) -> Any:
        r = await client.get(path, headers=headers)
        r.raise_for_status()
        return r.json().get("data")
