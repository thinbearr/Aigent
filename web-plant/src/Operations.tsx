import { useState } from "react";
import { api, useLive } from "./api";
import { Chip, Dot, useToast } from "./kit";

const CAN = (r: string) => ["operator", "supervisor", "engineer", "admin"].includes(r);
const stateTone: Record<string, string> = { normal: "good", outside_normal: "warn", alarm: "warn", trip: "bad" };

export default function Operations({ role }: { role: string }) {
  const toast = useToast();
  const { data: s, reload } = useLive<any>(() => api.get("/api/plant/state"), 1500);
  const can = CAN(role);
  const setSp = async (tag: string, value: number) => { try { await api.post("/api/hmi/setpoint", { tag, value }); toast(`${tag} set to ${value}`, "ok"); reload(); } catch (e: any) { toast(e.message, "err"); } };
  const coil = async (c: string, on: boolean) => { try { await api.post("/api/hmi/coil", { coil: c, on }); reload(); } catch (e: any) { toast(e.message, "err"); } };
  const ack = async (id: number) => { try { await api.post(`/api/hmi/alarms/${id}/ack`); reload(); } catch (e: any) { toast(e.message, "err"); } };
  if (!s) return <div className="sub p-8">Loading process state…</div>;

  return (
    <div className="space-y-4">
      <div className="flex items-end justify-between">
        <div>
          <div className="eyebrow mb-2">Kaveri · Line 2 · Purdue L2</div>
          <h1 className="display text-3xl md:text-4xl">Operations</h1>
          <p className="sub mt-1.5">SCADA / HMI supervisory control</p>
        </div>
        <div className="flex gap-2">
          <Chip tone={s.safety.sis_tripped ? "bad" : "good"}>{s.safety.sis_tripped ? "SIS TRIPPED" : "SIS Armed"}</Chip>
          <Chip tone="neutral">Logic v{s.program.version}</Chip>
        </div>
      </div>

      {/* process values */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        {s.tags.map((t: any) => (
          <div key={t.key} className="tile p-4">
            <div className="flex items-center justify-between"><span className="sub">{t.label}</span><Dot tone={stateTone[t.state] || "good"} /></div>
            <div className="objnum mt-3" style={{ color: t.state === "trip" ? "#a23b2e" : t.state === "alarm" || t.state === "outside_normal" ? "#b5703a" : "#1a1a1e" }}>
              {t.value}<span className="text-sm font-sans font-normal text-sub ml-1">{t.unit}</span></div>
            <div className="sub mt-2 font-mono text-[11px]">{t.tag} · nom {t.normal[0]}–{t.normal[1]}</div>
          </div>
        ))}
      </div>

      <div className="grid lg:grid-cols-2 gap-4">
        {/* setpoints */}
        <div className="tile">
          <div className="tile-h"><span className="tile-t">Setpoints</span>{!can && <Chip tone="warn">Read-only</Chip>}</div>
          <div className="p-4 space-y-5">
            <Sp label="Temperature" unit="°C" value={s.setpoints.temp_sp} min={40} max={85} step={0.5} disabled={!can} onSet={(v: number) => setSp("temp_sp", v)} />
            <Sp label="Conveyor speed" unit="m/s" value={s.setpoints.conveyor_sp} min={0} max={1.4} step={0.05} disabled={!can} onSet={(v: number) => setSp("conveyor_sp", v)} />
            <Sp label="Feed pump" unit="%" value={s.setpoints.pump_speed_sp} min={0} max={100} step={5} disabled={!can} onSet={(v: number) => setSp("pump_speed_sp", v)} />
          </div>
        </div>

        {/* actuators + production */}
        <div className="space-y-4">
          <div className="tile">
            <div className="tile-h"><span className="tile-t">Actuators</span></div>
            <div className="p-4 grid grid-cols-3 gap-3">
              {[["heater_enable", "Heater", s.actuators.heater_enable], ["pump_run", "Pump", s.actuators.pump_run], ["conveyor_run", "Conveyor", s.actuators.conveyor_run]].map(([k, l, on]: any) => (
                <button key={k} disabled={!can} onClick={() => coil(k, !on)}
                  className={`py-3 rounded-lg border text-sm font-medium transition disabled:opacity-40 ${on ? "border-good/40 bg-green-50 text-good" : "border-line2 bg-gray-50 text-sub"}`}>
                  <div className="flex items-center justify-center gap-1.5"><Dot tone={on ? "good" : "off"} />{l}</div>
                  <div className="text-[11px] mt-1">{on ? "Running" : "Off"}</div></button>))}
            </div>
          </div>
          <div className="tile p-4 flex items-center gap-6">
            <div><div className="sub">Bottles produced</div><div className="objnum text-brand mt-1">{s.production.bottles}</div></div>
            <div><div className="sub">Rejects</div><div className="objnum mt-1">{s.production.rejects}</div></div>
            <div><div className="sub">Heater output</div><div className="objnum mt-1">{s.actuators.heater_out?.toFixed(0)}<span className="text-sm text-sub">%</span></div></div>
          </div>
        </div>
      </div>

      {/* alarms */}
      <div className="tile">
        <div className="tile-h"><span className="tile-t">Active alarms</span><Chip tone={s.alarms.length ? "warn" : "good"}>{s.alarms.length}</Chip></div>
        <table className="w-full">
          <thead><tr>{["Severity", "Message", "Time", "Status", ""].map(h => <th key={h} className="th">{h}</th>)}</tr></thead>
          <tbody>
            {s.alarms.length === 0 && <tr><td colSpan={5} className="td text-center text-sub py-5">No active alarms</td></tr>}
            {s.alarms.map((a: any) => (
              <tr key={a.id}>
                <td className="td"><Chip tone={a.level === "trip" ? "bad" : "warn"}>{a.level}</Chip></td>
                <td className="td">{a.message}</td>
                <td className="td text-sub">{new Date(a.ts).toLocaleTimeString()}</td>
                <td className="td text-sub">{a.acked_by ? `Ack ${a.acked_by}` : "Unacknowledged"}</td>
                <td className="td text-right">{!a.acked_by && can && <button className="btn-default h-7" onClick={() => ack(a.id)}>Acknowledge</button>}</td>
              </tr>))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Sp({ label, unit, value, min, max, step, onSet, disabled }: any) {
  const [v, setV] = useState(value); const dirty = Math.abs(v - value) > 1e-6;
  return (
    <div>
      <div className="flex items-baseline justify-between mb-2"><span className="text-sm">{label}</span>
        <span className="text-lg font-semibold tabular-nums text-brand">{value} <span className="text-sm text-sub">{unit}</span></span></div>
      <div className="flex items-center gap-3">
        <input type="range" min={min} max={max} step={step} defaultValue={value} disabled={disabled} onChange={e => setV(+e.target.value)} className="flex-1 accent-brand disabled:opacity-40" />
        <button className={`btn h-8 min-w-[88px] justify-center ${dirty ? "btn-emph" : "btn-default"}`} disabled={disabled || !dirty} onClick={() => onSet(v)}>{dirty ? `Set ${v}` : "Set"}</button>
      </div>
    </div>
  );
}
