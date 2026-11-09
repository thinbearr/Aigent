"""Background threads: the simulation tick, the historian sampler and noise bots."""
import random
import threading
import time

from . import settings
from .db import session_scope
from .events import emit
from .models import Alarm, ProductionOrder, TagSample, utcnow
from .plant.sim import RANGES, plant

_stop = threading.Event()
_threads: list[threading.Thread] = []
PAUSE_NOISE = threading.Event()   # set while a benchmark controls the range


def _sim_loop():
    last = time.monotonic()
    while not _stop.is_set():
        now = time.monotonic()
        try:
            plant.tick(now - last)
        except Exception:
            pass
        last = now
        _stop.wait(settings.SIM_TICK_SECONDS)


def _historian_loop():
    while not _stop.is_set():
        try:
            snap = plant.snapshot()
            with session_scope() as s:
                for tag in RANGES:
                    s.add(TagSample(tag=tag, value=round(plant.reported_value(tag), 3)))
                s.add(TagSample(tag="bottles", value=snap["bottles"]))
                s.add(TagSample(tag="heater_out", value=round(snap["heater_out"], 2)))
                cutoff = utcnow().timestamp() - settings.HISTORIAN_RETENTION_HOURS * 3600
                old = s.query(TagSample).filter(TagSample.ts < utcnow().fromtimestamp(cutoff, tz=utcnow().tzinfo)).limit(500).all()
                for o in old:
                    s.delete(o)
        except Exception:
            pass
        _stop.wait(settings.HISTORIAN_INTERVAL)


def organic_event():
    """One piece of routine activity by the simulated staff, so the evidence is never empty or trivially clean."""
    roll = random.random()
    try:
        if roll < 0.35:
            with session_scope() as s:
                al = s.query(Alarm).filter(Alarm.active.is_(True), Alarm.acked_by.is_(None)).first()
                if al:
                    al.acked_by = "p.nair"
                    al.acked_at = utcnow()
                    tag = al.tag
                    emit(source="hmi", host="hmi-01", event_type="alarm_ack", actor="p.nair", src_ip="10.20.0.10", tag=tag)
                    return
            roll = 0.5
        if roll < 0.55:
            emit(source="auth", host="erp-01", event_type="login_success", actor="a.kulkarni", src_ip="10.40.1.11",
                 protocol="https", outcome="success", method="corp", note="routine")
        elif roll < 0.7:
            emit(source="historian", host="historian-01", event_type="report_view", actor="r.mehta", src_ip="10.40.0.30",
                 protocol="https", outcome="info")
        elif roll < 0.85:
            emit(source="erp", host="erp-01", event_type="production_order_released", actor="a.kulkarni", src_ip="10.40.1.11",
                 protocol="https", outcome="success", note="routine")
        else:
            cur = plant.snapshot()["temp_sp"]
            new = round(min(78, max(68, cur + random.choice([-0.5, 0.5]))), 1)
            plant.write(1, "hr", 0, [int(new * 10)], {"src_ip": "10.20.0.10", "actor": "p.nair",
                        "protocol": "modbus/tcp", "function_code": 6})
    except Exception:
        pass


def organic_burst(n: int = 4):
    for _ in range(n):
        organic_event()


def _noise_loop():
    while not _stop.is_set():
        _stop.wait(random.uniform(settings.NOISE_MIN, settings.NOISE_MAX))
        if _stop.is_set():
            break
        if not PAUSE_NOISE.is_set():
            organic_event()


def start():
    if _threads:
        return
    _stop.clear()
    for fn in (_sim_loop, _historian_loop, _noise_loop):
        t = threading.Thread(target=fn, daemon=True, name=fn.__name__)
        t.start()
        _threads.append(t)


def stop():
    _stop.set()
    for t in _threads:
        t.join(timeout=2)
    _threads.clear()
