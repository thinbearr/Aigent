# OpenPLC and Docker: STATUS = UNTESTED

Docker is not installed on the machine this project was built on. **Nothing in this document, `Dockerfile`, `docker-compose.yml` or
`plc/MixTankControl.st` has been built, started or run against a real OpenPLC runtime.** Do not cite it as working.

## What exists

* `src/cyberarena/range/kaveri/plant/plc_bridge.py`: a Modbus/TCP client that, when `PLC_BACKEND=openplc`, plays the field I/O. It writes the
  process measurements into an external PLC every 200 ms and reads the actuator commands back, so the physics stays in Python and the
  controller is external. The register map is in the module docstring.
* `tests/test_bridge.py` **does pass**: it exercises the client against a small in-process Modbus/TCP stand-in. That proves the byte-level
  client logic only, not any OpenPLC behaviour.
* `plc/MixTankControl.st`: an unverified Structured Text sketch matching that map.
* `docker-compose.yml`: a profile `openplc` that needs `OPENPLC_IMAGE` set by you.

## Checklist before this can be called working

1. Pick the OpenPLC runtime image or install per the OpenPLC project's current instructions; set `OPENPLC_IMAGE`.
2. Compile `MixTankControl.st` in the OpenPLC editor; fix located addresses to your runtime (OpenPLC documents `%QW0-1023` as holding registers and `%IW0-1023` as input registers at Modbus addresses 0-1023, check your version).
3. Start with `PLC_BACKEND=openplc`; confirm `plc_bridge.STATE['connected']` and that the heater command moves the simulated temperature.
4. Re-run the range scenarios against it and compare evidence with the built-in PLC. Writes to the runtime will not produce the plant's own `setpoint_change` events unless you add them: **the benchmark was run only on the built-in PLC.**
