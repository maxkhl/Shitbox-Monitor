import asyncio
import logging

import uvicorn
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from registry import Registry
from sources import Source
from sources.pi import PiStatusSource
from sources.router import TeltonikaSource
from sources.shelly import ShellySource
from sources.victron import VictronBleSource

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

app = FastAPI(title="Camper Monitor")
registry = Registry()

SOURCES: list[Source] = [
    VictronBleSource(),
    TeltonikaSource(),
    ShellySource(),
    PiStatusSource(),
]

for source in SOURCES:
    source.register_routes(app, registry)


@app.on_event("startup")
async def startup() -> None:
    for source in SOURCES:
        asyncio.create_task(source.run(registry))


@app.get("/api/data")
def get_data() -> JSONResponse:
    return JSONResponse(content=registry.snapshot())


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "sources_seen": len(registry.snapshot())}


app.mount("/", StaticFiles(directory="static", html=True), name="static")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
