import { useState } from "react";
import { dev, getDevToken, setDevToken, useLive } from "./api";
import { Chip, Dot, Modal, useToast } from "./kit";

export default function RangeControl() {
  const toast = useToast();
  const status = useLive<any>(() => dev.get("/dev/status"), 3000);
  const [tok, setTok] = useState(getDevToken());
  if (status.err)
    return (
      <div className="max-w-md mx-auto mt-10 tile p-6">
        <h2 className="tile-t">Range Control is protected</h2>
        <p className="sub mt-1">Enter the developer token (separate from operator logins). The agent never receives it.</p>
        <input className="input mt-4" value={tok} onChange={e => setTok(e.target.value)} placeholder="x-dev-token" />
        <div className="sub mt-2">Default (dev): arena-dev-token</div>
        <button className="btn-primary w-full justify-center mt-3" onClick={() => { setDevToken(tok); status.reload(); }}>Unlock</button>
      </div>
    );
  return (
    <div className="space-y-4">
      <div className="flex items-end justify-between flex-wrap gap-2">
        <div>
          <div className="eyebrow mb-2">Developer Mode · Ground Truth</div>
          <h1 className="display text-3xl md:text-4xl">Range Control</h1>
          <p className="sub mt-1.5 max-w-xl">Configure the known conditions the plant is in — breach points, attack / maintenance scenarios, faults. This is what the investigation agent must discover.</p></div>
        <div className="flex items-center gap-4">
          <Metric k="Events" v={status.data?.event_count} /><Metric k="Cases" v={status.data?.case_count} />
          <Metric k="Process T" v={`${status.data?.process?.temperature ?? "–"}°C`} />
          <ResetBtn onDone={() => { status.reload(); toast("Range reset to baseline", "ok"); }} />
        </div>
      </div>
      <div className="grid xl:grid-cols-[1.5fr_1fr] gap-4">
        <Switchboard onChange={status.reload} />
        <Scenarios onRun={status.reload} />
      </div>
      <Speed status={status.data} onChange={status.reload} />
    </div>
  );
}
function Metric({ k, v }: { k: string; v: any }) { return <div className="text-right"><div className="sub text-[11px]">{k}</div><div className="text-sm font-semibold tabular-nums">{v ?? "–"}</div></div>; }

function Switchboard({ onChange }: { onChange: () => void }) {
  const toast = useToast();
  const { data, reload } = useLive<any>(() => dev.get("/dev/breach-points"), 0);
  const set = async (key: string, mode: string) => { try { await dev.post("/dev/breach-points", { changes: { [key]: mode } }); reload(); onChange(); } catch (e: any) { toast(e.message, "err"); } };
  const preset = async (p: string) => { try { await dev.post("/dev/preset", { preset: p }); reload(); onChange(); toast(`Preset applied: ${p}`, "ok"); } catch (e: any) { toast(e.message, "err"); } };
  const bulk = async (m: string) => { const changes = Object.fromEntries((data?.breach_points || []).map((b: any) => [b.key, m])); await dev.post("/dev/breach-points", { changes }); reload(); onChange(); };
  return (
    <div className="tile">
      <div className="tile-h"><span className="tile-t">Breach-point switchboard</span><Chip tone="neutral">11 · L4→L0</Chip>
        <div className="ml-auto flex gap-1.5"><button className="btn-bad h-7" onClick={() => bulk("vulnerable")}>All open</button>
          <button className="btn-good h-7" onClick={() => bulk("patched")}>All safe</button></div></div>
      <div className="px-4 py-2.5 border-b border-line flex items-center gap-1.5 flex-wrap bg-gray-50/60">
        <span className="sub mr-1">Presets:</span>
        {Object.entries(data?.presets || {}).map(([k, v]: any) => <button key={k} title={v.description} onClick={() => preset(k)}
          className="text-xs px-2.5 py-1 rounded-full border border-line2 bg-white hover:border-brand text-sub">{v.label}</button>)}
      </div>
      <div className="divide-y divide-line max-h-[480px] overflow-auto">
        {data?.breach_points?.map((b: any) => {
          const vuln = b.mode === "vulnerable";
          return (
            <div key={b.key} className="px-4 py-3 flex items-start gap-3">
              <span className="font-mono text-xs text-sub bg-gray-100 rounded px-1.5 py-0.5 mt-0.5">{b.key}</span>
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium">{b.title}</div>
                <div className="sub mt-0.5">{vuln ? b.vulnerable : b.patched}</div>
                <div className="flex gap-1 mt-1 flex-wrap"><Chip tone="neutral">{b.layer}</Chip><Chip tone="neutral">{b.asset}</Chip></div>
              </div>
              <button onClick={() => set(b.key, vuln ? "patched" : "vulnerable")}
                className={`shrink-0 w-24 h-8 rounded text-xs font-semibold border ${vuln ? "border-bad/40 bg-red-50 text-bad" : "border-good/40 bg-green-50 text-good"}`}>
                <span className="flex items-center justify-center gap-1"><Dot tone={vuln ? "bad" : "good"} />{vuln ? "Vulnerable" : "Patched"}</span></button>
            </div>);
        })}
      </div>
    </div>
  );
}

function Scenarios({ onRun }: { onRun: () => void }) {
  const toast = useToast();
  const { data, reload } = useLive<any>(() => dev.get("/dev/scenarios"), 3000);
  const [running, setRunning] = useState<string | null>(null);
  const [result, setResult] = useState<any | null>(null);
  const run = async (key: string) => { setRunning(key); try { const r = await dev.post("/dev/scenarios/run", { key, fast: true }); setResult(r); reload(); onRun(); toast(`Scenario ${key} executed · ${r.events_generated} events`, "ok"); } catch (e: any) { toast(e.message, "err"); } finally { setRunning(null); } };
  return (
    <div className="tile">
      <div className="tile-h"><span className="tile-t">Scenario launcher</span><Chip tone="neutral">ATT&CK ICS</Chip></div>
      <div className="max-h-[540px] overflow-auto divide-y divide-line">
        {data?.scenarios?.map((s: any) => (
          <div key={s.key} className="px-4 py-3">
            <div className="flex items-center gap-2">
              <span className="font-mono text-xs text-sub">{s.key}</span>
              <Chip tone={s.is_attack ? "bad" : "good"}>{s.is_attack ? "Attack" : "Benign"}</Chip>
              <span className="text-sm font-medium flex-1 truncate">{s.name}</span>
              <button className="btn-primary h-7" disabled={!!running} onClick={() => run(s.key)}>{running === s.key ? "…" : "Run"}</button></div>
            <div className="sub mt-1">{s.summary}</div>
            <div className="sub text-[11px] mt-0.5">Purdue {s.purdue_path?.join(" → ")}{!s.runnable && <span className="text-warn"> · needs {s.blocked_by_patched?.join(",")} open</span>}</div>
          </div>))}
      </div>
      <Modal open={!!result} onClose={() => setResult(null)} title={`Scenario ${result?.scenario} executed`} wide>
        <div className="flex gap-2 mb-3"><Chip tone={result?.is_attack ? "bad" : "good"}>{result?.is_attack ? "Attack" : "Legitimate maintenance"}</Chip>
          <Chip tone="info">{result?.events_generated} events logged</Chip><span className="sub self-center font-mono">{result?.case_key}</span></div>
        <ol className="border-l-2 border-line pl-4 space-y-2">
          {result?.steps?.map((st: any, i: number) => <li key={i} className="text-sm relative">
            <span className="absolute -left-[22px] top-1.5"><Dot tone={st.outcome === "blocked" ? "bad" : st.outcome === "success" ? "good" : "info"} /></span>
            {st.action}{st.purdue && <span className="sub"> · {st.purdue}</span>}</li>)}
        </ol>
        <p className="sub mt-4">The agent at <span className="font-mono">:8200</span> can now investigate this — it reads only the evidence, not this screen.</p>
      </Modal>
    </div>
  );
}

function Speed({ status, onChange }: { status: any; onChange: () => void }) {
  const toast = useToast();
  const [fault, setFault] = useState({ tag: "temperature", kind: "drift", value: 5 });
  const setSpeed = async (v: number) => { await dev.post("/dev/plant/speed", { speed: v }); onChange(); };
  const inject = async () => { await dev.post("/dev/plant/fault", fault); toast("Sensor fault injected", "ok"); };
  const clear = async () => { await dev.post("/dev/plant/fault", { tag: fault.tag, kind: "clear" }); toast("Fault cleared", "ok"); };
  return (
    <div className="tile p-4 grid md:grid-cols-2 gap-6">
      <div><div className="lbl">Simulation speed</div>
        <div className="flex gap-2">{[1, 2, 5, 10, 20].map(v => <button key={v} onClick={() => setSpeed(v)}
          className={`btn h-8 ${status?.speed === v ? "btn-emph" : "btn-default"}`}>{v}×</button>)}</div>
        <p className="sub mt-2">Speeds up the process physics so a scenario reaches its impact faster.</p></div>
      <div><div className="lbl">Inject sensor fault (non-attack anomaly)</div>
        <div className="grid grid-cols-3 gap-2">
          <select className="input" value={fault.tag} onChange={e => setFault({ ...fault, tag: e.target.value })}>{["temperature", "pressure", "level", "conveyor_speed", "motor_current"].map(t => <option key={t}>{t}</option>)}</select>
          <select className="input" value={fault.kind} onChange={e => setFault({ ...fault, kind: e.target.value })}>{["drift", "stuck"].map(k => <option key={k}>{k}</option>)}</select>
          <input className="input" type="number" value={fault.value} onChange={e => setFault({ ...fault, value: +e.target.value })} /></div>
        <div className="flex gap-2 mt-2"><button className="btn-emph h-8" onClick={inject}>Inject</button><button className="btn-default h-8" onClick={clear}>Clear</button></div>
        <p className="sub mt-1">Tests whether the agent raises a false positive on a benign fault.</p></div>
    </div>
  );
}
function ResetBtn({ onDone }: { onDone: () => void }) {
  const [b, setB] = useState(false);
  return <button className="btn-bad h-8" disabled={b} onClick={async () => { setB(true); try { await dev.post("/dev/reset"); onDone(); } finally { setB(false); } }}>{b ? "…" : "Reset range"}</button>;
}
