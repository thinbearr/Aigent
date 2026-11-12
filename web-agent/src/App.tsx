import { useEffect, useRef, useState } from "react";
import { agent, useLive } from "./api";
import { Avatar, Dial, Chip, Weight, AGENTS } from "./components";

type Phase = "idle" | "red" | "redDone" | "thinking" | "done";

export default function App() {
  const plant = useLive<any>(() => agent.plant(), 4000);
  const [critic, setCritic] = useState(true);
  const [phase, setPhase] = useState<Phase>("idle");
  const [result, setResult] = useState<any | null>(null);
  const [red, setRed] = useState<any | null>(null);
  const [redCursor, setRedCursor] = useState(0);
  const [alertIdx, setAlertIdx] = useState(0);
  const [cursor, setCursor] = useState(0);
  const [err, setErr] = useState<string | null>(null);
  const timer = useRef<any>(null);

  const primary = result?.alerts?.[alertIdx];
  const steps = primary?.steps || [];

  const runRed = async () => {
    setErr(null); setRed(null); setResult(null); setPhase("red"); setRedCursor(0);
    try {
      const r = await agent.redteam();
      setRed(r);
      let i = 0;
      timer.current = setInterval(() => {
        i += 1; setRedCursor(i);
        if (i >= r.attempts.length) { clearInterval(timer.current); setTimeout(() => setPhase("redDone"), 500); }
      }, 260);
    } catch (e: any) { setErr(e.message); setPhase("idle"); }
  };

  const investigate = async () => {
    setErr(null); setResult(null); setPhase("thinking"); setCursor(0); setAlertIdx(0);
    try {
      const r = await agent.investigate(critic);
      if (!r.alerts?.length) { setResult(r); setPhase("done"); return; }
      setResult(r);
      // reveal the reasoning trace progressively
      const total = r.alerts[0].steps.length;
      const per = total > 50 ? 45 : total > 25 ? 80 : 130;
      let i = 0;
      timer.current = setInterval(() => {
        i += 1; setCursor(i);
        if (i >= total) { clearInterval(timer.current); setTimeout(() => setPhase("done"), 400); }
      }, per);
    } catch (e: any) { setErr(e.message); setPhase("idle"); }
  };
  const skip = () => { clearInterval(timer.current); setCursor(steps.length); setPhase("done"); };
  useEffect(() => () => clearInterval(timer.current), []);
  useEffect(() => { if (phase === "done") window.scrollTo({ top: 0, behavior: "smooth" }); }, [phase]);

  return (
    <div className="min-h-screen">
      <Header plant={plant.data} />
      <main className="max-w-[1180px] mx-auto px-5 pb-20">
        {phase === "idle" && <Intake plant={plant.data} critic={critic} setCritic={setCritic} onRed={runRed} onGo={investigate} err={err} />}
        {phase === "red" && <RedRunning red={red} cursor={redCursor} />}
        {phase === "redDone" && red && <RedReport red={red} onInvestigate={investigate} onAgain={() => setPhase("idle")} />}
        {phase === "thinking" && <Thinking steps={steps} cursor={cursor} onSkip={skip} critic={critic} />}
        {phase === "done" && result && (
          result.alerts?.length
            ? <Report r={result} idx={alertIdx} setIdx={setAlertIdx} onAgain={() => setPhase("idle")} critic={critic} red={red} />
            : <Clean r={result} onAgain={() => setPhase("idle")} />
        )}
      </main>
    </div>
  );
}

function Header({ plant }: { plant: any }) {
  const ok = plant?.connected;
  return (
    <header className="sticky top-0 z-20 backdrop-blur bg-canvas/80 border-b border-line">
      <div className="max-w-[1180px] mx-auto px-5 h-16 flex items-center gap-3">
        <div className="w-9 h-9 rounded-xl bg-iris grid place-items-center text-white font-bold shadow-lift">◈</div>
        <div>
          <div className="font-bold text-lg leading-none">CyberArena <span className="grad-text">Agent</span></div>
          <div className="label mt-1">autonomous ICS investigation</div>
        </div>
        <div className="ml-auto flex items-center gap-2">
          <span className="pill" style={{ borderColor: ok ? "#12b88633" : "#f43f6e33", background: ok ? "#12b8860d" : "#f43f6e0d", color: ok ? "#0f9e76" : "#f43f6e" }}>
            <span className="w-2 h-2 rounded-full" style={{ background: ok ? "#12b886" : "#f43f6e" }} />
            {ok ? "Plant linked" : "Plant offline"}
          </span>
          <span className="mono text-xs text-faint hidden sm:inline">{plant?.plant_url}</span>
        </div>
      </div>
    </header>
  );
}

function Intake({ plant, critic, setCritic, onRed, onGo, err }: any) {
  const by = plant?.by_source || {};
  const total = plant?.event_count ?? 0;
  const connected = plant?.connected;
  return (
    <div className="pt-12 animate-rise">
      <div className="text-center max-w-2xl mx-auto">
        <div className="label">neither agent is told which flaws are open</div>
        <h1 className="text-5xl font-bold mt-3 leading-tight">Red breaks in.<br /><span className="grad-text">Blue finds out.</span></h1>
        <p className="text-sub mt-4 text-lg">The Red agent probes every exploit against the live factory — only the open flaws let it through. Then Blue → Critic → Forensics investigates the aftermath, blind, amid normal plant traffic.</p>
      </div>

      {/* two-step action */}
      <div className="grid md:grid-cols-2 gap-4 mt-10 max-w-3xl mx-auto">
        <div className="card p-6 flex flex-col" style={{ boxShadow: "0 18px 50px -28px rgba(244,63,110,.5)" }}>
          <div className="flex items-center gap-2"><span className="w-9 h-9 rounded-xl grid place-items-center text-lg" style={{ background: "#f43f6e18", color: "#f43f6e" }}>⚔</span>
            <div><div className="font-bold">Red agent</div><div className="label">autonomous penetration test</div></div></div>
          <p className="text-sm text-sub mt-3 flex-1">Tries all 12 exploit techniques in attacker order — recon, initial access, lateral movement, impact. Blind to the switchboard.</p>
          <button className="btn px-5 h-12 mt-4 text-base text-white shadow-lift" style={{ background: "#f43f6e" }}
            disabled={!connected} onClick={onRed}>⚔ Launch attack</button>
        </div>
        <div className="card p-6 flex flex-col">
          <div className="flex items-center gap-2"><span className="w-9 h-9 rounded-xl grid place-items-center text-lg bg-iris/10 text-iris">✦</span>
            <div><div className="font-bold">Blue agent</div><div className="label">defensive investigation</div></div></div>
          <p className="text-sm text-sub mt-3 flex-1">Reads the evidence left behind and works out which flaws were breached — without ever seeing the attack plan or the switches.</p>
          <div className="flex items-center gap-3 mt-4">
            <button onClick={() => setCritic(!critic)} className="flex items-center gap-2 group shrink-0">
              <span className={`w-10 h-5.5 rounded-full transition-colors relative ${critic ? "bg-iris" : "bg-slate-300"}`} style={{ height: 22 }}>
                <span className={`absolute top-0.5 w-5 h-5 rounded-full bg-white shadow transition-all ${critic ? "left-[18px]" : "left-0.5"}`} /></span>
              <span className="text-xs font-medium">Critic {critic ? "on" : "off"}</span></button>
            <button className="btn-soft px-5 h-12 text-base ml-auto" disabled={!connected || !total} onClick={onGo}>✦ Investigate</button>
          </div>
        </div>
      </div>
      {err && <div className="mt-3 text-sm text-rose text-center">⚠ {err}</div>}

      <div className="card p-4 mt-4 max-w-3xl mx-auto flex items-center gap-6 flex-wrap">
        <span className="label">target factory</span>
        <span className="mono text-xs text-faint">{plant?.plant_url}</span>
        <span className="text-sm"><b className="tabular-nums">{total}</b> <span className="text-faint">events</span></span>
        <span className="text-sm"><b className="tabular-nums">{plant?.tickets ?? 0}</b> <span className="text-faint">tickets</span></span>
        <div className="flex flex-wrap gap-1.5 ml-auto">
          {Object.entries(by).map(([k, n]: any) => <Chip key={k} tone="slate">{k} · {n}</Chip>)}
        </div>
      </div>
    </div>
  );
}

const RES_TONE: Record<string, string> = { success: "#f43f6e", blocked: "#12b886", failed: "#9a9aad", error: "#f59f0a" };
const TACTIC_LABEL: Record<string, string> = { recon: "Recon", "initial-access": "Initial access", "credential-access": "Credential access", "lateral-movement": "Lateral movement", "defense-evasion": "Defense evasion", impact: "Impact" };

function AttemptLine({ a, live }: { a: any; live?: boolean }) {
  const col = RES_TONE[a.result];
  const icon = a.result === "success" ? "✓" : a.result === "blocked" ? "✕" : a.result === "failed" ? "–" : "!";
  return (
    <div className={`flex items-center gap-3 px-3 py-2 rounded-xl ${live ? "animate-pop" : ""}`} style={{ background: a.result === "success" ? "#f43f6e0a" : undefined }}>
      <span className="w-6 h-6 rounded-lg grid place-items-center text-xs font-bold shrink-0" style={{ background: `${col}1a`, color: col }}>{icon}</span>
      <span className="label w-28 shrink-0 hidden sm:block">{TACTIC_LABEL[a.tactic] || a.tactic}</span>
      <span className="text-sm flex-1 min-w-0 truncate">{a.title}{a.flaw && <span className="mono text-xs text-faint"> · {a.flaw}</span>}</span>
      <span className="text-xs font-semibold uppercase tracking-wide shrink-0" style={{ color: col }}>{a.result}</span>
    </div>
  );
}

function RedRunning({ red, cursor }: any) {
  const shown = (red?.attempts || []).slice(0, cursor);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => { ref.current?.scrollTo({ top: ref.current.scrollHeight, behavior: "smooth" }); }, [cursor]);
  return (
    <div className="pt-10 animate-rise">
      <div className="flex items-center gap-3 justify-center">
        <div className="relative w-12 h-12">
          <div className="absolute inset-0 rounded-full border-2" style={{ borderColor: "#f43f6e22" }} />
          <div className="absolute inset-0 rounded-full border-2 border-transparent animate-orbit" style={{ borderTopColor: "#f43f6e" }} />
          <div className="absolute inset-0 grid place-items-center animate-breathe" style={{ color: "#f43f6e" }}>⚔</div>
        </div>
        <div><div className="font-semibold text-lg">Red agent attacking…</div><div className="label">probing every exploit — blind to the switchboard</div></div>
      </div>
      <div ref={ref} className="card mt-6 max-w-3xl mx-auto p-2 max-h-[62vh] overflow-auto">
        {shown.map((a: any, i: number) => <AttemptLine key={i} a={a} live={i === shown.length - 1} />)}
      </div>
    </div>
  );
}

function RedReport({ red, onInvestigate, onAgain }: any) {
  const broke = red.breached_flaws?.length > 0;
  return (
    <div className="pt-8 animate-rise space-y-5">
      <div className="card p-6" style={{ boxShadow: broke ? "0 18px 50px -24px rgba(244,63,110,.45)" : "0 18px 50px -24px rgba(18,184,134,.4)" }}>
        <div className="flex items-center gap-2 flex-wrap">
          <Chip tone={broke ? "rose" : "mint"}>{broke ? "⚔ Breach achieved" : "✓ Factory held"}</Chip>
          <span className="label ml-auto">{red.techniques_tried} techniques tried</span>
        </div>
        <div className="text-xl font-semibold mt-3">{red.summary}</div>
        {broke && (
          <div className="mt-4">
            <div className="label mb-2">flaws the red agent broke through</div>
            <div className="flex flex-wrap gap-2">
              {red.breached_flaws.map((f: string) => <span key={f} className="mono text-sm font-bold px-2.5 py-1 rounded-lg" style={{ background: "#f43f6e14", color: "#f43f6e" }}>{f}</span>)}
            </div>
          </div>)}
      </div>

      <div className="card p-5">
        <div className="label mb-3">attack log · every technique it tried</div>
        <div className="space-y-1">{red.attempts.map((a: any, i: number) => <AttemptLine key={i} a={a} />)}</div>
      </div>

      <div className="card p-5 flex items-center gap-4 flex-wrap" style={{ background: "linear-gradient(100deg,#5b5bf00a,#2aa7ff0a)" }}>
        <span className="w-10 h-10 rounded-xl bg-iris/10 text-iris grid place-items-center text-lg">✦</span>
        <div className="flex-1 min-w-[220px]"><div className="font-semibold">Hand off to the Blue agent</div>
          <div className="text-sm text-sub">It will investigate the evidence blind and try to name the same flaws — with no knowledge of what Red just did.</div></div>
        <button className="btn-iris px-6 h-12 text-base" onClick={onInvestigate}>✦ Investigate the aftermath →</button>
      </div>
      <div className="text-center"><button className="btn-soft px-5 h-10" onClick={onAgain}>← Back</button></div>
    </div>
  );
}

function Thinking({ steps, cursor, onSkip, critic }: any) {
  const shown = steps.slice(0, cursor);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => { ref.current?.scrollTo({ top: ref.current.scrollHeight, behavior: "smooth" }); }, [cursor]);
  const current = steps[cursor - 1];
  return (
    <div className="pt-10 animate-rise">
      <div className="flex items-center gap-3 justify-center">
        <div className="relative w-12 h-12">
          <div className="absolute inset-0 rounded-full border-2 border-iris/20" />
          <div className="absolute inset-0 rounded-full border-2 border-transparent border-t-iris animate-orbit" />
          <div className="absolute inset-0 grid place-items-center text-iris animate-breathe">◈</div>
        </div>
        <div>
          <div className="font-semibold text-lg">Investigating…</div>
          <div className="label">{current ? (AGENTS[current.agent]?.name || current.agent) : "orchestrating"}</div>
        </div>
        <button className="btn-soft px-4 h-9 ml-6 text-sm" onClick={onSkip}>Skip to verdict</button>
      </div>

      <div ref={ref} className="card mt-6 max-w-3xl mx-auto p-2 max-h-[62vh] overflow-auto">
        {shown.map((s: any, i: number) => <StepRow key={i} s={s} last={i === shown.length - 1} />)}
      </div>
    </div>
  );
}

function StepRow({ s, last }: { s: any; last: boolean }) {
  const a = AGENTS[s.agent] || AGENTS.System;
  const kindTone: Record<string, string> = { tool: "slate", challenge: "amber", evidence: "sky", verdict: "iris", report: "iris" };
  return (
    <div className={`flex gap-3 px-3 py-2 rounded-xl ${last ? "animate-pop bg-iris/[0.04]" : ""}`}>
      <Avatar agent={s.agent} sm />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold" style={{ color: a.color }}>{s.agent}</span>
          {s.kind !== "message" && <Chip tone={kindTone[s.kind] || "slate"}>{s.kind}</Chip>}
        </div>
        <div className="text-sm text-ink mt-0.5 break-words">{s.text}</div>
        {s.why && <div className="text-xs text-faint mt-0.5 italic">{s.why}</div>}
      </div>
    </div>
  );
}

function Flaws({ flaws }: { flaws: any[] }) {
  if (!flaws?.length) return null;
  const sevTone: Record<string, string> = { critical: "rose", high: "amber", medium: "sky", low: "slate" };
  const sevRing: Record<string, string> = { critical: "#f43f6e", high: "#f59f0a", medium: "#2aa7ff", low: "#9a9aad" };
  return (
    <div className="card p-5">
      <div className="flex items-center gap-2 mb-1">
        <div className="label">security flaws the agent identified as violated</div>
        <span className="ml-auto chip bg-iris/10 text-iris">{flaws.length} found</span>
      </div>
      <p className="text-xs text-faint mb-4">Inferred purely from the evidence — the agent was never told which switches are on.</p>
      <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {flaws.map((f) => (
          <div key={f.code} className="rounded-xl border border-line p-3.5 animate-pop" style={{ boxShadow: `inset 3px 0 0 ${sevRing[f.severity]}` }}>
            <div className="flex items-center gap-2">
              <span className="mono text-xs font-bold px-1.5 py-0.5 rounded" style={{ background: `${sevRing[f.severity]}1a`, color: sevRing[f.severity] }}>{f.code}</span>
              <Chip tone={sevTone[f.severity]}>{f.severity}</Chip>
              <span className="label ml-auto">{f.layer}</span>
            </div>
            <div className="font-semibold text-sm mt-2 leading-snug">{f.title}</div>
            <div className="text-xs text-sub mt-1">{f.why}</div>
            <div className="label mt-2">{f.observations} observation{f.observations > 1 ? "s" : ""} · {f.event_ids.slice(0, 4).join(", ")}</div>
          </div>))}
      </div>
    </div>
  );
}

function RemediationPlaybook({ alert }: { alert: any }) {
  const list: string[] = alert.checklist?.length ? alert.checklist : (alert.actions || []);
  const [checked, setChecked] = useState<Record<number, boolean>>({});
  const [operatorName, setOperatorName] = useState("");
  const [signed, setSigned] = useState(false);

  const toggle = (idx: number) => {
    if (signed) return;
    setChecked(prev => ({ ...prev, [idx]: !prev[idx] }));
  };

  const allDone = list.length > 0 && list.every((_: any, i: number) => checked[i]);

  return (
    <div className="card p-5 border-2" style={{ borderColor: alert.incident ? "#f43f6e40" : "#12b88640" }}>
      <div className="flex items-center gap-2 mb-2">
        <span className="w-2.5 h-2.5 rounded-full" style={{ background: alert.incident ? "#f43f6e" : "#12b886" }} />
        <div className="label">Operator Mitigation Checklist · Physical Verification</div>
        <span className="label ml-auto tabular-nums font-bold">
          {Object.values(checked).filter(Boolean).length}/{list.length} done
        </span>
      </div>

      <p className="text-xs text-sub mb-3">
        Tailored to machine asset playbooks across Purdue L1-L4. Complete physical inspections before restoring operations.
      </p>

      <div className="space-y-2 mb-4 max-h-60 overflow-y-auto pr-1">
        {list.map((step: string, idx: number) => (
          <label key={idx} className="flex items-start gap-2.5 p-2 rounded-xl border border-line cursor-pointer hover:bg-slate-50 transition-colors">
            <input
              type="checkbox"
              checked={!!checked[idx]}
              onChange={() => toggle(idx)}
              disabled={signed}
              className="mt-1 h-4 w-4 rounded text-iris focus:ring-iris border-gray-300"
            />
            <span className={`text-xs flex-1 ${checked[idx] ? "line-through text-faint" : "text-ink"}`}>
              {step}
            </span>
          </label>
        ))}
      </div>

      <div className="pt-3 border-t border-line flex flex-wrap items-center gap-2">
        <input
          type="text"
          placeholder="Operator / Shift Supervisor Name"
          value={operatorName}
          onChange={e => setOperatorName(e.target.value)}
          disabled={signed}
          className="text-xs px-2.5 py-1.5 rounded-lg border border-line bg-slate-50 text-ink focus:outline-none focus:border-iris flex-1 min-w-[170px]"
        />
        <button
          onClick={() => setSigned(true)}
          disabled={!allDone || !operatorName.trim() || signed}
          className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold shadow-sm transition-all ${
            signed
              ? "bg-mint/20 text-mint cursor-default"
              : allDone && operatorName.trim()
              ? "bg-iris text-white hover:opacity-90"
              : "bg-slate-100 text-faint cursor-not-allowed"
          }`}
        >
          {signed ? "✓ Verified & Signed" : "Sign-Off & Clear Case"}
        </button>
      </div>

      {signed && (
        <div className="mt-2 text-[11px] text-mint font-medium animate-pop">
          ✓ Signed off by {operatorName}. Containment protocol completed.
        </div>
      )}

      <div className="label mt-3 mb-1">impact assessment</div>
      <div className="text-xs text-sub">{alert.impact}</div>
    </div>
  );
}

function Report({ r, idx, setIdx, onAgain, critic, red }: any) {
  const a = r.alerts[idx];
  const incident = a.incident;
  const blueFlaws = (r.flaws || []).map((f: any) => f.code);
  const redFlaws: string[] = red?.breached_flaws || [];
  const matched = redFlaws.length ? redFlaws.filter((f) => blueFlaws.includes(f)) : [];
  return (
    <div className="pt-8 animate-rise space-y-5">
      {/* verdict hero */}
      <div className="card p-6 flex flex-col md:flex-row items-center gap-6" style={{ boxShadow: incident ? "0 18px 50px -24px rgba(244,63,110,.4)" : "0 18px 50px -24px rgba(18,184,134,.4)" }}>
        <Dial value={a.confidence} incident={incident} />
        <div className="flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <Chip tone={incident ? "rose" : "mint"}>{incident ? "⚠ Security incident" : "✓ No incident — authorised activity"}</Chip>
            <Chip tone={critic ? "amber" : "slate"}>Critic {critic ? "on" : "off"}</Chip>
            {r.alerts.length > 1 && (
              <div className="flex gap-1 ml-auto">
                {r.alerts.map((_: any, i: number) => <button key={i} onClick={() => setIdx(i)}
                  className={`w-7 h-7 rounded-lg text-xs font-semibold ${i === idx ? "bg-iris text-white" : "bg-slate-100 text-sub"}`}>{i + 1}</button>)}
              </div>)}
          </div>
          <div className="text-xl font-semibold mt-3">{a.summary}</div>
          <div className="text-sm text-sub mt-2 mono">alert · {a.alert}</div>
          <div className="flex gap-5 mt-4 text-sm">
            <Meta k="evidence" v={a.evidence.length} /><Meta k="tool calls" v={a.tool_calls} />
            <Meta k="alternatives tested" v={a.alternatives.length} /><Meta k="assets" v={a.affected_assets.length} />
          </div>
        </div>
      </div>

      {red && (
        <div className="card p-5">
          <div className="label mb-3">red broke in vs. blue detected</div>
          <div className="flex items-center gap-4 flex-wrap">
            <div><div className="label mb-1" style={{ color: "#f43f6e" }}>red broke</div>
              <div className="flex gap-1.5 flex-wrap">{redFlaws.map((f) => <span key={f} className="mono text-xs font-bold px-2 py-0.5 rounded" style={{ background: "#f43f6e14", color: "#f43f6e" }}>{f}</span>)}</div></div>
            <span className="text-2xl text-faint">→</span>
            <div><div className="label mb-1 text-iris">blue detected</div>
              <div className="flex gap-1.5 flex-wrap">{blueFlaws.map((f: string) => <span key={f} className="mono text-xs font-bold px-2 py-0.5 rounded" style={{ background: redFlaws.includes(f) ? "#12b88618" : "#f59f0a18", color: redFlaws.includes(f) ? "#12b886" : "#f59f0a" }}>{f}</span>)}</div></div>
            <div className="ml-auto text-right"><div className="text-2xl font-bold" style={{ color: matched.length === redFlaws.length && redFlaws.length ? "#12b886" : "#f59f0a" }}>{matched.length}/{redFlaws.length}</div><div className="label">caught</div></div>
          </div>
        </div>)}

      <Flaws flaws={r.flaws} />

      {a.attack_path?.length > 0 && (
        <div className="card p-5">
          <div className="label mb-3">reconstructed path</div>
          <div className="flex items-center gap-2 flex-wrap">
            {a.attack_path.map((h: string, i: number) => (
              <span key={i} className="flex items-center gap-2">
                <span className="mono text-sm px-2.5 py-1.5 rounded-lg bg-slate-50 border border-line">{h}</span>
                {i < a.attack_path.length - 1 && <span className="text-iris">→</span>}
              </span>))}
          </div>
        </div>)}

      <div className="grid lg:grid-cols-2 gap-5">
        {/* evidence */}
        <div className="card p-5">
          <div className="label mb-3">evidence · every conclusion cites these</div>
          <div className="space-y-2">
            {a.evidence.map((e: any) => (
              <div key={e.id} className="flex items-start gap-3 p-2.5 rounded-xl hover:bg-slate-50">
                <Weight w={e.weight} />
                <div className="flex-1">
                  <div className="text-sm">{e.text}</div>
                  <div className="label mt-1">{e.kind}{e.events?.length ? ` · ${e.events.join(", ")}` : ""}</div>
                </div>
              </div>))}
          </div>
        </div>

        {/* alternatives */}
        <div className="card p-5">
          <div className="label mb-3">alternatives the Critic tested</div>
          {a.alternatives.length === 0 && <div className="text-sm text-faint">Critic was disabled for this run.</div>}
          <div className="space-y-2">
            {a.alternatives.map((alt: any) => {
              const rejected = /reject/i.test(alt.outcome);
              return (
                <div key={alt.id} className="flex items-start gap-3 p-2.5 rounded-xl border border-line">
                  <span className="mt-0.5">{rejected ? "✗" : "✓"}</span>
                  <div><div className="text-sm font-medium">{alt.label}</div>
                    <div className="text-xs mt-0.5" style={{ color: rejected ? "#f43f6e" : "#12b886" }}>{alt.outcome}</div></div>
                </div>);
            })}
          </div>
          {a.mitre?.length > 0 && <>
            <div className="label mt-5 mb-2">MITRE ATT&CK for ICS</div>
            <div className="flex flex-wrap gap-1.5">{a.mitre.map((m: any) => <Chip key={m.id} tone="iris">{m.id} {m.name}</Chip>)}</div>
          </>}
        </div>
      </div>

      {/* timeline */}
      {a.timeline?.length > 0 && (
        <div className="card p-5">
          <div className="label mb-3">timeline</div>
          <div className="space-y-0">
            {a.timeline.map((t: any, i: number) => (
              <div key={i} className="flex gap-3 pb-3 relative">
                <div className="flex flex-col items-center">
                  <span className="w-2.5 h-2.5 rounded-full bg-iris mt-1.5" />
                  {i < a.timeline.length - 1 && <span className="w-px flex-1 bg-line my-1" />}
                </div>
                <div className="flex-1 pb-1">
                  <div className="text-sm">{t.text}</div>
                  <div className="label mt-0.5">{t.t} · {t.asset} · {t.evidence?.join(", ")}</div>
                </div>
              </div>))}
          </div>
        </div>)}

      {/* actions + audit */}
      <div className="grid lg:grid-cols-2 gap-5">
        <RemediationPlaybook alert={a} />
        <div className="card p-5">
          <div className="label mb-3">tool-call audit · all read-only</div>
          <div className="max-h-56 overflow-auto space-y-1">
            {a.audit.map((au: any) => (
              <div key={au.n} className="mono text-xs flex gap-2 py-1 border-b border-line/60">
                <span className="text-faint w-5">{au.n}</span>
                <span className="text-iris w-16 shrink-0">{au.agent}</span>
                <span className="flex-1 truncate">{au.tool} <span className="text-faint">· {au.summary}</span></span>
                <span className={au.status === "ok" ? "text-mint" : "text-rose"}>{au.status}</span>
              </div>))}
          </div>
        </div>
      </div>

      <div className="flex justify-center pt-2">
        <button className="btn-soft px-6 h-11" onClick={onAgain}>↻ New investigation</button>
      </div>
      <p className="text-center text-xs text-faint">The agent never changes anything in the plant. A human approves or reopens every case.</p>
    </div>
  );
}

function Meta({ k, v }: { k: string; v: any }) { return <div><div className="font-bold tabular-nums">{v}</div><div className="label">{k}</div></div>; }

function Clean({ r, onAgain }: any) {
  return (
    <div className="pt-20 text-center animate-rise">
      <div className="w-16 h-16 rounded-2xl bg-mint/10 text-mint grid place-items-center text-3xl mx-auto">✓</div>
      <h2 className="text-2xl font-bold mt-4">No alert raised</h2>
      <p className="text-sub mt-2 max-w-md mx-auto">The agent examined {r.evidence_examined} events and {r.tickets_available} tickets. Nothing matched a detection rule — the plant looks quiet. Configure a condition on the Plant console and investigate again.</p>
      <button className="btn-soft px-6 h-11 mt-6" onClick={onAgain}>Back</button>
    </div>
  );
}
