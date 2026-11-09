(* SKETCH, NOT COMPILED, NOT RUN. Written to match src/cyberarena/range/kaveri/plant/plc_bridge.py.
   Check it in the OpenPLC editor before use; the located addresses may need adjusting for your runtime version.
   Holding registers (Modbus address = register number):
     %QW0..3   setpoints written by the bridge: temp_sp x10, conveyor_sp x100, pump_speed_sp, auto_mode
     %QW10..13 measurements written by the bridge: temperature x10, pressure x100, level x10, conveyor_speed x100
     %QW20     heater_out 0..100 (written by this program)
   Coils: %QX0.0 heater_enable, %QX0.1 pump_run, %QX0.2 conveyor_run                                           *)
PROGRAM MixTankControl
  VAR
    temp_sp      AT %QW0  : INT;
    temperature  AT %QW10 : INT;
    heater_out   AT %QW20 : INT;
    heater_en    AT %QX0.0 : BOOL;
    pump_run     AT %QX0.1 : BOOL;
    conv_run     AT %QX0.2 : BOOL;
    err          : INT;
    integ        : INT := 48;
  END_VAR
  err := temp_sp - temperature;                 (* x10 units *)
  integ := LIMIT(0, integ + err / 20, 100);
  heater_out := LIMIT(0, err * 6 / 10 + integ, 100);
  heater_en := TRUE;
  pump_run := TRUE;
  conv_run := TRUE;
END_PROGRAM

CONFIGURATION Config0
  RESOURCE Res0 ON PLC
    TASK Main(INTERVAL := T#100ms, PRIORITY := 0);
    PROGRAM Inst0 WITH Main : MixTankControl;
  END_RESOURCE
END_CONFIGURATION
