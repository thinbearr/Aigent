"""`cyberarena range ...`: list / generate / serve the simulated range."""
from __future__ import annotations


def main(a):
    if a.action == "list":
        from . import families
        for k, f in families.REGISTRY.items():
            print(f"{k}  {'ATTACK' if f.attack else 'benign'}  {'hard' if f.hard else '    '}  {f.name}: {f.description}")
        return 0
    if a.action == "generate":
        from . import generate
        n = generate.generate(a.out, seeds=[a.seed], keys=a.scenarios, preset=a.preset)
        print(f"wrote {n} cases to {a.out}")
        return 0
    if a.action == "serve":
        import threading

        import uvicorn

        from .kaveri.main import dev_app, plant_app
        threading.Thread(target=lambda: uvicorn.run(dev_app, host=a.host, port=8100, log_level="warning"), daemon=True).start()
        print(f"PLANT (simulation) · plant API :8000 · Developer Mode API :8100 (token arena-dev-token) · Modbus/TCP :5020")
        uvicorn.run(plant_app, host=a.host, port=8000, log_level="warning")
        return 0
    return 1
