# Shitbox Monitor

Tiny FastAPI service that scrapes data from sensors and devices in a camper van and
exposes them as a single JSON snapshot. Comes with a web dashboard. Designed to run
on a Raspberry Pi (currently a Pi Zero 2 W).

Companion Android app + home-screen widget lives in a separate repo:
**shitbox-monitor-android**.

## Data sources

Each source is a small Python module under `sources/` that publishes its current
state into a shared `Registry`. Add new sources by implementing `Source.run(registry)`
and appending an instance to `SOURCES` in `main.py`.

Built-in sources:

- **`sources/victron.py`** — Victron BLE devices (SmartShunt, MPPT, …) via the
  `victron-ble` library. Reads advertised state and decrypts using per-device keys.
- **`sources/router.py`** — Teltonika router (tested on RUTX11, RutOS 7.x) via its
  REST API. Publishes GPS and mobile/LTE state.

## Running

```sh
cp .env.example .env
# edit .env: router credentials, Victron BLE devices
docker compose up -d
```

The dashboard is at `http://<pi-ip>:8000`. The JSON API is at
`http://<pi-ip>:8000/api/data`.

## API shape

`GET /api/data` returns a flat object keyed by source-id:

```json
{
  "victron.smartshunt": {
    "name": "SmartShunt",
    "type": "BatteryMonitor",
    "data": { "soc": 84.0, "voltage": 13.2, "current": -1.4, ... },
    "updated_at": "2026-05-26T20:00:01"
  },
  "router.gps":    { "name": "GPS",    "type": "GPS",    "data": { ... } },
  "router.mobile": { "name": "Mobile", "type": "Mobile", "data": { ... } }
}
```

No history — only the latest snapshot. Designed for clients that poll.

## Hardware notes

- Runs fine on a Raspberry Pi Zero 2 W with the bind-mount setup in
  `docker-compose.yml`. BLE access requires `privileged: true` + the host
  D-Bus socket. `network_mode: host` is the simplest way to give the container
  access to both the BLE stack and the router on LAN.
- The Dockerfile uses [piwheels](https://www.piwheels.org/) as a wheel index
  to avoid compiling `pydantic-core` etc. from source on ARM — without it,
  the first `pip install` on a Pi Zero can take hours.

## Adding a new source

```python
# sources/foo.py
from sources import Source
from registry import Registry

class FooSource(Source):
    async def run(self, registry: Registry) -> None:
        while True:
            data = await fetch_foo()  # however you get it
            registry.publish(
                "foo.thing",
                name="Foo Thing",
                type="Foo",
                data=data,
            )
            await asyncio.sleep(10)
```

Then in `main.py`:
```python
from sources.foo import FooSource
SOURCES.append(FooSource())
```

The dashboard renders unknown source types as a generic key/value card, so new
sources show up immediately without UI changes.
