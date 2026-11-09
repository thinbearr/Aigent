"""PLC backend selector and the Modbus/TCP bridge to an external PLC runtime (e.g. OpenPLC).

PLC_BACKEND=builtin (default)  the pure-Python PLC in sim.py runs the control logic. Nothing to start.
PLC_BACKEND=openplc            the control logic runs on an external Modbus/TCP PLC. This bridge plays the field I/O:
                               every cycle it writes the process measurements into the PLC and reads the actuator
                               commands back, so the physics (level 0) stays here and the *controller* is real.

Register map (all Modbus addresses are 0-based, scaled integers, matching plc/MixTankControl.st):
    holding registers written by the bridge (sensors, the PLC program only reads them):
        10 temperature x10, 11 pressure x100, 12 level x10, 13 conveyor_speed x100
    holding registers read by the bridge (actuator outputs the PLC program writes):
        20 heater_out (0-100), 21 pump_speed (0-100), 22 conveyor_ref x100
    coils read by the bridge:  0 heater_enable, 1 pump_run, 2 conveyor_run
    holding registers 0-3 are the operator setpoints (temp_sp x10, conveyor_sp x100, pump_speed_sp, auto_mode)

STATUS: the client is exercised against this project's own Modbus server in tests/test_bridge.py. It has NOT been run
against a real OpenPLC runtime (Docker was not available where this was built); see docs/OPENPLC.md for the checklist.
"""
from __future__ import annotations

import socket
import struct
import threading
import time

from .. import settings


class ModbusClient:
    def __init__(self, host: str, port: int, unit: int = 1, timeout: float = 2.0):
        self.host, self.port, self.unit, self.timeout = host, port, unit, timeout
        self.sock: socket.socket | None = None
        self.tid = 0

    def _conn(self):
        if self.sock is None:
            self.sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        return self.sock

    def _rpc(self, pdu: bytes) -> bytes:
        self.tid = (self.tid + 1) & 0xFFFF
        try:
            s = self._conn()
            s.sendall(struct.pack(">HHHB", self.tid, 0, len(pdu) + 1, self.unit) + pdu)
            hdr = self._recvn(s, 7)
            length = struct.unpack(">HHHB", hdr)[2]
            body = self._recvn(s, length - 1)
        except OSError:
            self.close()
            raise
        if body[0] & 0x80:
            raise IOError(f"modbus exception {body[1]} for function {pdu[0]}")
        return body

    @staticmethod
    def _recvn(s, n):
        buf = b""
        while len(buf) < n:
            chunk = s.recv(n - len(buf))
            if not chunk:
                raise OSError("connection closed")
            buf += chunk
        return buf

    def close(self):
        if self.sock:
            try:
                self.sock.close()
            finally:
                self.sock = None

    def read_holding(self, addr, count):
        b = self._rpc(struct.pack(">BHH", 3, addr, count))
        return list(struct.unpack(">" + "H" * count, b[2:2 + count * 2]))

    def read_input(self, addr, count):
        b = self._rpc(struct.pack(">BHH", 4, addr, count))
        return list(struct.unpack(">" + "H" * count, b[2:2 + count * 2]))

    def read_coils(self, addr, count):
        b = self._rpc(struct.pack(">BHH", 1, addr, count))
        return [(b[2 + i // 8] >> (i % 8)) & 1 for i in range(count)]

    def write_register(self, addr, value):
        self._rpc(struct.pack(">BHH", 6, addr, value & 0xFFFF))

    def write_registers(self, addr, values):
        self._rpc(struct.pack(">BHHB", 16, addr, len(values), len(values) * 2) + b"".join(struct.pack(">H", v & 0xFFFF) for v in values))

    def write_coil(self, addr, on):
        self._rpc(struct.pack(">BHH", 5, addr, 0xFF00 if on else 0))


STATE = dict(backend=settings.PLC_BACKEND, connected=False, cycles=0, last_error=None, last_cycle=None)
_stop = threading.Event()
_thread: threading.Thread | None = None


def _cycle(c: ModbusClient, plant):
    snap = plant.snapshot()
    # setpoints and process measurements -> PLC
    c.write_registers(0, [int(snap["temp_sp"] * 10), int(snap["conveyor_sp"] * 100), int(snap["pump_speed_sp"]), int(snap["auto_mode"])])
    c.write_registers(10, [int(snap["temperature"] * 10), int(snap["pressure"] * 100), int(snap["level"] * 10), int(snap["conveyor_speed"] * 100)])
    # actuator commands <- PLC
    out = c.read_holding(20, 3)
    coils = c.read_coils(0, 3)
    with plant.lock:
        plant.s["heater_out"] = float(max(0, min(100, out[0])))
        plant.s["heater_enable"] = bool(coils[0])
        plant.s["pump_run"] = bool(coils[1])
        plant.s["conveyor_run"] = bool(coils[2])
    STATE.update(connected=True, cycles=STATE["cycles"] + 1, last_error=None, last_cycle=time.time())


def _loop():
    from .sim import plant
    c = ModbusClient(settings.OPENPLC_HOST, settings.OPENPLC_PORT)
    plant.external_control = True
    while not _stop.is_set():
        try:
            _cycle(c, plant)
        except Exception as exc:
            STATE.update(connected=False, last_error=f"{type(exc).__name__}: {exc}")
        _stop.wait(0.2)


def start():
    global _thread
    if settings.PLC_BACKEND != "openplc" or (_thread and _thread.is_alive()):
        return
    _stop.clear()
    _thread = threading.Thread(target=_loop, daemon=True, name="plc-bridge")
    _thread.start()


def stop():
    _stop.set()
