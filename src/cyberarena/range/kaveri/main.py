"""ArenaPlant backend.

Two FastAPI apps on two ports:
  - Plant app (8000): operator/engineer UI + read-only /evidence for agents.
  - Developer Mode app (8100): range control + ground truth. Never expose to agents.
The Modbus/TCP server (5020) runs alongside for real protocol clients.
"""
import asyncio
import threading

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import runtime, seed, settings
from .plant.modbus_server import serve as serve_modbus
from .routers import auth_routes, dev, engineering, erp, evidence, plant_routes

CORS = dict(allow_origins=["*"], allow_methods=["*"], allow_headers=["*"], allow_credentials=False)

plant_app = FastAPI(title="ArenaPlant - Kaveri Process Industries", version="1.0.0",
                    description="Simulated IT/OT manufacturing plant with configurable breach points.")
plant_app.add_middleware(CORSMiddleware, **CORS)
for r in (auth_routes.router, erp.router, plant_routes.router, engineering.router, evidence.router):
    plant_app.include_router(r)

dev_app = FastAPI(title="ArenaPlant - Developer Mode", version="1.0.0",
                  description="Range Control Center. Isolated from the agents.")
dev_app.add_middleware(CORSMiddleware, **CORS)
dev_app.include_router(dev.router)


@plant_app.get("/api/health")
def health():
    return {"status": "ok", "service": "plant"}


@plant_app.get("/api/topology")
def topology_public():
    from .topology import topology
    return topology()


_started = False
_modbus_thread: threading.Thread | None = None


def _bootstrap():
    global _started, _modbus_thread
    if _started:
        return
    _started = True
    seed.init_database()
    runtime.start()
    from .plant import plc_bridge
    plc_bridge.start()

    def _run_modbus():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(serve_modbus(settings.MODBUS_HOST, settings.MODBUS_PORT))

    _modbus_thread = threading.Thread(target=_run_modbus, daemon=True, name="modbus")
    _modbus_thread.start()


@plant_app.on_event("startup")
def _startup_plant():
    _bootstrap()


@dev_app.on_event("startup")
def _startup_dev():
    _bootstrap()


# --- single-process mode: serve the built React app from the plant app (no nginx/Docker needed)
from pathlib import Path as _Path  # noqa: E402

from fastapi.responses import FileResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

_dist = _Path(settings.FRONTEND_DIST)
if (_dist / "index.html").exists():
    plant_app.mount("/assets", StaticFiles(directory=_dist / "assets"), name="assets")

    @plant_app.get("/{full_path:path}", include_in_schema=False)
    def _spa(full_path: str):
        if full_path.startswith(("api/", "evidence/", "dev/")):
            from fastapi import HTTPException
            raise HTTPException(404)
        f = _dist / full_path
        return FileResponse(f if f.is_file() else _dist / "index.html")
