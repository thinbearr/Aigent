"""The Modbus bridge, exercised against a tiny in-process Modbus/TCP slave that behaves like a PLC runtime."""
import socketserver
import struct
import threading

from cyberarena.range.kaveri.plant import plc_bridge
from cyberarena.range.kaveri.plant.sim import Plant


class Slave(socketserver.BaseRequestHandler):
    hr = {}
    coils = {}

    def handle(self):
        try:
            while True:
                h = self.request.recv(7)
                if len(h) < 7:
                    return
                tid, _, ln, unit = struct.unpack(">HHHB", h)
                pdu = self.request.recv(ln - 1)
                fc = pdu[0]
                if fc == 3:
                    a, n = struct.unpack(">HH", pdu[1:5])
                    # the "PLC program": heater command follows the temperature error
                    sp, t = self.hr.get(0, 0), self.hr.get(10, 0)
                    self.hr[20] = max(0, min(100, int((sp - t) * 0.5)))   # registers are x10, so this is 5 % per degree
                    self.coils.update({0: 1, 1: 1, 2: 1})
                    vals = [self.hr.get(a + i, 0) for i in range(n)]
                    r = bytes([3, n * 2]) + b"".join(struct.pack(">H", v) for v in vals)
                elif fc == 1:
                    a, n = struct.unpack(">HH", pdu[1:5])
                    bits = sum(self.coils.get(a + i, 0) << i for i in range(n))
                    r = bytes([1, 1, bits])
                elif fc == 16:
                    a, n, _ = struct.unpack(">HHB", pdu[1:6])
                    for i in range(n):
                        self.hr[a + i] = struct.unpack(">H", pdu[6 + 2 * i:8 + 2 * i])[0]
                    r = pdu[:5]
                else:
                    r = bytes([fc | 0x80, 1])
                self.request.sendall(struct.pack(">HHHB", tid, 0, len(r) + 1, unit) + r)
        except OSError:
            pass


def test_bridge_cycle_drives_heater_from_external_plc():
    srv = socketserver.ThreadingTCPServer(("127.0.0.1", 0), Slave)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        c = plc_bridge.ModbusClient("127.0.0.1", srv.server_address[1])
        p = Plant()
        p.s["temp_sp"], p.s["temperature"] = 72.0, 60.0
        plc_bridge._cycle(c, p)
        assert Slave.hr[0] == 720 and Slave.hr[10] == 600          # setpoint and measurement reached the PLC
        plc_bridge._cycle(c, p)
        assert p.s["heater_out"] == 60.0                            # actuator command came back: (72-60) degC * 5 %/degC
        assert plc_bridge.STATE["connected"] and plc_bridge.STATE["cycles"] >= 2
    finally:
        srv.shutdown()
