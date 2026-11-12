import { useEffect, useRef, useState } from "react";
import { agent, useLive } from "./api";
import { Avatar, Dial, Chip, Weight, AGENTS } from "./components";

type Phase = "idle" | "red" | "redDone" | "thinking" | "done";

export default function App() {
  const plant = useLive<any>(() => agent.plant(), 4000);
  const [connected, setConnected] = useState(false);
  const [view, setView] = useState<"app" | "about">("app");
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
  useEffect(() => { window.scrollTo({ top: 0 }); }, [view, connected]);

  const disconnect = async () => {
    try { await agent.disconnect(); } catch {}
    clearInterval(timer.current);
    setConnected(false); setPhase("idle"); setRed(null); setResult(null); plant.reload();
  };

  return (
    <div className="min-h-screen relative">
      <CanvasBg />
      <CustomCursor />
      <Boot />
      <Header plant={plant.data} connected={connected} view={view} setView={setView} onDisconnect={disconnect} />
      <main className="relative z-10 max-w-[1180px] mx-auto px-5 pb-24">
        {view === "about" ? (
          <About onBack={() => setView("app")} />
        ) : !connected ? (
          <Landing onConnected={() => { setConnected(true); plant.reload(); }} onAbout={() => setView("about")} />
        ) : (
          <>
            {phase === "idle" && <Intake plant={plant.data} critic={critic} setCritic={setCritic} onRed={runRed} onGo={investigate} err={err} />}
            {phase === "red" && <RedRunning red={red} cursor={redCursor} />}
            {phase === "redDone" && red && <RedReport red={red} onInvestigate={investigate} onAgain={() => setPhase("idle")} />}
            {phase === "thinking" && <Thinking steps={steps} cursor={cursor} onSkip={skip} critic={critic} />}
            {phase === "done" && result && (
              result.alerts?.length
                ? <Report r={result} idx={alertIdx} setIdx={setAlertIdx} onAgain={() => setPhase("idle")} critic={critic} red={red} />
                : <Clean r={result} onAgain={() => setPhase("idle")} />
            )}
          </>
        )}
      </main>
    </div>
  );
}

function Header({ plant, connected, view, setView, onDisconnect }: any) {
  const ok = connected && plant?.connected;
  return (
    <header className="sticky top-0 z-20 backdrop-blur-md bg-canvas/70 border-b border-line">
      <div className="max-w-[1180px] mx-auto px-5 h-16 flex items-center gap-3">
        <button className="flex items-center gap-3 text-left" onClick={() => setView("app")}>
          <div className="w-9 h-9 rounded-xl bg-iris grid place-items-center text-canvas font-semibold">◈</div>
          <div>
            <div className="font-medium text-lg leading-none tracking-tight">CyberArena <span className="grad-text">Agent</span></div>
            <div className="label mt-1.5">autonomous ICS investigation</div>
          </div>
        </button>
        <nav className="ml-auto flex items-center gap-1 sm:gap-2">
          <button onClick={() => setView(view === "about" ? "app" : "about")}
            className={`px-3 h-9 rounded-full text-sm transition-colors ${view === "about" ? "text-iris" : "text-sub hover:text-ink"}`}>About</button>
          {connected ? (
            <span className="pill border-iris/25 bg-iris/[0.06] text-iris">
              <span className="w-2 h-2 rounded-full bg-iris" />
              {ok ? "Plant linked" : "Reconnecting…"}
            </span>
          ) : (
            <span className="pill border-line bg-white/[0.03] text-faint">
              <span className="w-2 h-2 rounded-full bg-faint" /> Not connected
            </span>
          )}
          {connected && <button onClick={onDisconnect} className="label hover:text-ink px-2">Disconnect</button>}
        </nav>
      </div>
    </header>
  );
}

function Intake({ plant, critic, setCritic, onRed, onGo, err }: any) {
  const by = plant?.by_source || {};
  const total = plant?.event_count ?? 0;
  const connected = plant?.connected;
  return (
    <div className="pt-16 animate-rise">
      <div className="text-center max-w-3xl mx-auto">
        <div className="label">neither agent is told which flaws are open</div>
        <h1 className="display text-6xl md:text-7xl mt-5">Red breaks in.<br /><span className="grad-text">Blue finds out.</span></h1>
        <p className="text-sub mt-6 text-lg max-w-2xl mx-auto leading-relaxed">The Red agent probes every exploit against the live factory — only the open flaws let it through. Then Blue → Critic → Forensics investigates the aftermath, blind, amid normal plant traffic.</p>
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
              <span className={`w-10 h-5.5 rounded-full transition-colors relative ${critic ? "bg-iris" : "bg-white/15"}`} style={{ height: 22 }}>
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
  const sevRing: Record<string, string> = { critical: "#f2537a", high: "#f0b44a", medium: "#6bb6ff", low: "#67676a" };
  return (
    <div className="card p-5">
      <div className="flex items-center gap-2 mb-1">
        <div className="label">weaknesses the agent found were used</div>
        <span className="ml-auto chip bg-iris/10 text-iris font-mono text-[10px] uppercase tracking-wider">{flaws.length} found</span>
      </div>
      <p className="text-xs text-faint mb-4">In plain words — worked out purely from the evidence. The agent was never told which switches are on.</p>
      <div className="grid sm:grid-cols-2 gap-3">
        {flaws.map((f) => (
          <div key={f.code} className="rounded-xl border border-line p-4 animate-pop bg-white/[0.015]" style={{ boxShadow: `inset 3px 0 0 ${sevRing[f.severity]}` }}>
            <div className="flex items-center gap-2">
              <span className="mono text-xs font-bold px-1.5 py-0.5 rounded" style={{ background: `${sevRing[f.severity]}22`, color: sevRing[f.severity] }}>{f.code}</span>
              <Chip tone={sevTone[f.severity]}>{f.severity}</Chip>
              <span className="label ml-auto">{f.layer}</span>
            </div>
            {/* plain-language name anyone can read */}
            <div className="font-medium text-[15px] mt-3 leading-snug text-ink">{f.plain}</div>
            <div className="text-xs text-sub mt-1.5 leading-relaxed">{f.means}</div>
            <div className="mt-2.5 flex items-start gap-1.5 text-xs">
              <span className="text-iris shrink-0 font-mono uppercase tracking-wider text-[10px] mt-0.5">Fix</span>
              <span className="text-sub">{f.fix}</span>
            </div>
            <div className="label mt-2.5 text-faint">{f.title} · {f.observations} obs · {f.event_ids.slice(0, 3).join(", ")}</div>
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
          <label key={idx} className="flex items-start gap-2.5 p-2 rounded-xl border border-line cursor-pointer hover:bg-white/[0.04] transition-colors">
            <input
              type="checkbox"
              checked={!!checked[idx]}
              onChange={() => toggle(idx)}
              disabled={signed}
              className="mt-1 h-4 w-4 rounded accent-iris border-line bg-transparent"
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
          className="text-xs px-2.5 py-1.5 rounded-lg border border-line bg-white/[0.04] text-ink placeholder:text-faint focus:outline-none focus:border-iris flex-1 min-w-[170px]"
        />
        <button
          onClick={() => setSigned(true)}
          disabled={!allDone || !operatorName.trim() || signed}
          className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold shadow-sm transition-all ${
            signed
              ? "bg-mint/20 text-mint cursor-default"
              : allDone && operatorName.trim()
              ? "bg-iris text-canvas hover:opacity-90"
              : "bg-white/[0.06] text-faint cursor-not-allowed"
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
                  className={`w-7 h-7 rounded-lg text-xs font-semibold ${i === idx ? "bg-iris text-canvas" : "bg-white/[0.06] text-sub"}`}>{i + 1}</button>)}
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
                <span className="mono text-sm px-2.5 py-1.5 rounded-lg bg-white/[0.03] border border-line">{h}</span>
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
              <div key={e.id} className="flex items-start gap-3 p-2.5 rounded-xl hover:bg-white/[0.04]">
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

      <GptReport />

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

/* ───────────────────────── synchronized.studio flourishes ───────────────────────── */

// Intro loader: counts 0→100, then fades.
function Boot() {
  const [n, setN] = useState(0);
  const [gone, setGone] = useState(false);
  const [hide, setHide] = useState(false);
  useEffect(() => {
    let v = 0;
    const id = setInterval(() => {
      v = Math.min(100, v + Math.ceil(Math.random() * 7)); setN(v);
      if (v >= 100) { clearInterval(id); setTimeout(() => setGone(true), 280); setTimeout(() => setHide(true), 950); }
    }, 55);
    return () => clearInterval(id);
  }, []);
  if (hide) return null;
  return (
    <div className={`intro ${gone ? "gone" : ""}`}>
      <div className="flex items-end justify-between gap-4">
        <div>
          <div className="label mb-3">CyberArena · Agent</div>
          <div className="display text-[18vw] md:text-[12vw] leading-[0.85] text-ink tabular-nums">{n}</div>
        </div>
        <div className="text-right pb-2">
          <div className="label mb-1.5 text-iris">{n}%</div>
          <div className="text-sub text-sm leading-tight">Autonomous<br />ICS investigation</div>
        </div>
      </div>
    </div>
  );
}

// Custom cursor + mouse-follow glow ("the mouse thing").
function CustomCursor() {
  const dot = useRef<HTMLDivElement>(null);
  const ring = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!window.matchMedia("(hover: hover) and (pointer: fine)").matches) return;
    let rx = 0, ry = 0, tx = 0, ty = 0, raf = 0;
    const move = (e: MouseEvent) => {
      tx = e.clientX; ty = e.clientY;
      if (dot.current) dot.current.style.transform = `translate(${tx}px,${ty}px) translate(-50%,-50%)`;
      const t = e.target as HTMLElement;
      const hot = !!t.closest?.("button,a,input,label,[role=button]");
      ring.current?.classList.toggle("hot", hot);
    };
    const loop = () => {
      rx += (tx - rx) * 0.18; ry += (ty - ry) * 0.18;
      if (ring.current) ring.current.style.transform = `translate(${rx}px,${ry}px) translate(-50%,-50%)`;
      raf = requestAnimationFrame(loop);
    };
    window.addEventListener("mousemove", move); raf = requestAnimationFrame(loop);
    return () => { window.removeEventListener("mousemove", move); cancelAnimationFrame(raf); };
  }, []);
  return (<><div ref={ring} className="cursor-ring" /><div ref={dot} className="cursor-dot" /></>);
}

// Faint drifting constellation that reacts to the cursor.
function CanvasBg() {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const cv = ref.current; if (!cv) return;
    const ctx = cv.getContext("2d"); if (!ctx) return;
    let w = 0, h = 0, raf = 0;
    const N = 46;
    const pts = Array.from({ length: N }, () => ({ x: Math.random(), y: Math.random(), vx: (Math.random() - 0.5) * 0.0004, vy: (Math.random() - 0.5) * 0.0004 }));
    const mouse = { x: -1, y: -1 };
    const resize = () => { w = cv.width = window.innerWidth; h = cv.height = window.innerHeight; };
    const onMove = (e: MouseEvent) => { mouse.x = e.clientX; mouse.y = e.clientY; };
    resize();
    window.addEventListener("resize", resize);
    window.addEventListener("mousemove", onMove);
    const draw = () => {
      ctx.clearRect(0, 0, w, h);
      for (const p of pts) {
        p.x += p.vx; p.y += p.vy;
        if (p.x < 0 || p.x > 1) p.vx *= -1;
        if (p.y < 0 || p.y > 1) p.vy *= -1;
        const px = p.x * w, py = p.y * h;
        const d = Math.hypot(px - mouse.x, py - mouse.y);
        const near = mouse.x >= 0 && d < 170;
        ctx.beginPath();
        ctx.arc(px, py, near ? 1.8 : 1.1, 0, Math.PI * 2);
        ctx.fillStyle = near ? "rgba(222,235,200,0.55)" : "rgba(255,255,255,0.12)";
        ctx.fill();
        if (near) {
          ctx.beginPath(); ctx.moveTo(px, py); ctx.lineTo(mouse.x, mouse.y);
          ctx.strokeStyle = `rgba(222,235,200,${0.22 * (1 - d / 170)})`; ctx.lineWidth = 0.6; ctx.stroke();
        }
      }
      raf = requestAnimationFrame(draw);
    };
    draw();
    return () => { window.removeEventListener("resize", resize); window.removeEventListener("mousemove", onMove); cancelAnimationFrame(raf); };
  }, []);
  return <canvas ref={ref} className="fixed inset-0 z-0 pointer-events-none opacity-70" />;
}

// Minimal Markdown renderer for the GPT report.
function MarkdownView({ md }: { md: string }) {
  const inline = (s: string) =>
    s.split(/(\*\*[^*]+\*\*)/g).map((p, i) =>
      p.startsWith("**") && p.endsWith("**")
        ? <strong key={i} className="text-ink font-medium">{p.slice(2, -2)}</strong>
        : <span key={i}>{p}</span>);
  const blocks: any[] = [];
  let list: string[] = []; let k = 0;
  const flush = () => {
    if (list.length) {
      blocks.push(<ul key={k++} className="list-disc pl-5 space-y-1 my-2 text-sm text-sub marker:text-iris">{list.map((li, i) => <li key={i}>{inline(li)}</li>)}</ul>);
      list = [];
    }
  };
  for (const raw of md.split("\n")) {
    const l = raw.trimEnd();
    if (/^###\s/.test(l)) { flush(); blocks.push(<h4 key={k++} className="label text-iris mt-5 mb-1.5">{l.replace(/^###\s/, "")}</h4>); }
    else if (/^##\s/.test(l)) { flush(); blocks.push(<h3 key={k++} className="display text-2xl mt-6 mb-2 text-ink">{l.replace(/^##\s/, "")}</h3>); }
    else if (/^#\s/.test(l)) { flush(); blocks.push(<h2 key={k++} className="display text-3xl mt-2 mb-3 text-ink">{l.replace(/^#\s/, "")}</h2>); }
    else if (/^[-*]\s/.test(l)) { list.push(l.replace(/^[-*]\s/, "")); }
    else if (/^\d+\.\s/.test(l)) { list.push(l.replace(/^\d+\.\s/, "")); }
    else if (l.trim() === "") { flush(); }
    else { flush(); blocks.push(<p key={k++} className="text-sm text-sub leading-relaxed my-2">{inline(l)}</p>); }
  }
  flush();
  return <div>{blocks}</div>;
}

// GPT-written detailed incident report.
function GptReport() {
  const [state, setState] = useState<"idle" | "load" | "done" | "err">("idle");
  const [md, setMd] = useState(""); const [model, setModel] = useState(""); const [err, setErr] = useState("");
  const gen = async () => {
    setState("load"); setErr("");
    try { const r = await agent.report(); setMd(r.markdown); setModel(r.model); setState("done"); }
    catch (e: any) { setErr(e.message); setState("err"); }
  };
  return (
    <div className="card p-5">
      <div className="flex items-center gap-3 flex-wrap">
        <span className="w-9 h-9 rounded-xl bg-iris/10 text-iris grid place-items-center">✎</span>
        <div className="flex-1 min-w-[200px]">
          <div className="font-medium">Detailed incident report</div>
          <div className="text-sm text-sub">A plain-language write-up of this round, generated by GPT from the evidence.</div>
        </div>
        {state !== "done" && <button className="btn-iris px-5 h-11" disabled={state === "load"} onClick={gen}>{state === "load" ? "Writing…" : "Generate report"}</button>}
        {state === "done" && <span className="label">model · {model}</span>}
      </div>
      {state === "err" && <div className="text-sm text-rose mt-3">⚠ {err}</div>}
      {state === "load" && <div className="mt-4 space-y-2.5">{[...Array(5)].map((_, i) => <div key={i} className="h-3 rounded bg-white/[0.05] animate-pulse" style={{ width: `${92 - i * 11}%` }} />)}</div>}
      {state === "done" && <div className="mt-4 pt-4 border-t border-line max-h-[520px] overflow-auto pr-2"><MarkdownView md={md} /></div>}
    </div>
  );
}

/* ───────────────────────── landing + about ───────────────────────── */

const STEPS = [
  { color: "#f2537a", title: "Red breaks in", body: "An autonomous Red agent probes every exploit technique against the live factory — recon, access, lateral movement, impact. Only the open flaws let it through." },
  { color: "#deebc8", title: "Blue finds out", body: "Blue → Critic → Forensics reads the evidence left behind, challenges its own verdict, and names the flaws that were breached — blind, amid normal plant traffic." },
  { color: "#5fd39a", title: "A human decides", body: "The agent changes nothing in the plant. It produces a cited, auditable report; a person approves it or sends the case back." },
];

function Landing({ onConnected, onAbout }: any) {
  const [url, setUrl] = useState("http://localhost:8000");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const connect = async () => {
    setBusy(true); setErr("");
    try {
      const r = await agent.connect(url);
      if (r.connected) onConnected(r);
      else setErr(r.error || "could not reach the plant at that address");
    } catch (e: any) { setErr(e.message); }
    finally { setBusy(false); }
  };
  return (
    <div className="animate-rise">
      <div className="pt-16 md:pt-24 text-center max-w-3xl mx-auto">
        <div className="label">autonomous red vs blue · ICS / OT</div>
        <h1 className="display text-6xl md:text-8xl mt-5">Red breaks in.<br /><span className="grad-text">Blue finds out.</span></h1>
        <p className="text-sub mt-6 text-lg max-w-2xl mx-auto leading-relaxed">An autonomous investigation agent for industrial control systems. A Red agent attacks a live factory; Blue, Critic and Forensics work out what happened — blind, and citing every step.</p>
      </div>

      {/* connect panel — the agent reaches nothing until you connect it */}
      <div className="card p-6 md:p-7 mt-12 max-w-xl mx-auto">
        <div className="label text-iris">connect the agent to a plant</div>
        <p className="text-sm text-sub mt-2 leading-relaxed">Nothing is connected yet. Point the agent at a plant's evidence API and connect — for a live demo, paste the factory URL and go.</p>
        <div className="flex flex-col sm:flex-row gap-2 mt-4">
          <input value={url} onChange={e => setUrl(e.target.value)} onKeyDown={e => e.key === "Enter" && connect()}
            placeholder="http://localhost:8000"
            className="flex-1 h-12 px-4 rounded-full bg-white/[0.04] border border-line text-ink placeholder:text-faint mono text-sm focus:outline-none focus:border-iris transition" />
          <button className="btn-iris px-6 h-12 text-base shrink-0" disabled={busy || !url.trim()} onClick={connect}>{busy ? "Connecting…" : "Connect →"}</button>
        </div>
        {err && <div className="text-sm text-rose mt-3">⚠ {err}</div>}
        <div className="flex gap-2 mt-4 flex-wrap items-center">
          <span className="label mr-1">presets</span>
          {[["Local plant", "http://localhost:8000"], ["Docker network", "http://plant-api:8000"]].map(([l, u]) => (
            <button key={u} onClick={() => setUrl(u)} className="chip bg-white/[0.05] text-sub hover:text-iris">{l}</button>
          ))}
        </div>
      </div>

      <div className="grid md:grid-cols-3 gap-4 mt-16 max-w-4xl mx-auto">
        {STEPS.map((s, i) => (
          <div key={i} className="card p-5">
            <div className="label text-faint">0{i + 1}</div>
            <div className="font-medium text-xl mt-2.5" style={{ color: s.color }}>{s.title}</div>
            <p className="text-sm text-sub mt-2 leading-relaxed">{s.body}</p>
          </div>
        ))}
      </div>

      <div className="text-center mt-14">
        <button className="btn-soft px-5 h-11" onClick={onAbout}>About this project →</button>
      </div>
    </div>
  );
}

function About({ onBack }: any) {
  const facts = [
    { k: "Two services", v: "The plant (a disposable simulation) and the agent (the product) are separate systems that only talk over HTTP. Swap the plant for a real log source and the agent is unchanged." },
    { k: "Blind by design", v: "The agent never sees which flaws are switched on, which scenario ran, or what Red did. It reasons only from the evidence a plant would really expose." },
    { k: "Weighted evidence", v: "Every item of evidence carries a weight; confidence is a logistic function of them, and each verdict cites the evidence behind it." },
    { k: "Read-only", v: "The agent changes nothing in the plant. It investigates, reconstructs and reports — a human approves or reopens every case." },
  ];
  const agents = [
    { name: "Orchestrator", role: "plans and delegates; no direct access to the plant" },
    { name: "Blue", role: "single-pass analyst — gathers and scores evidence" },
    { name: "Critic", role: "argues the other side; demands checks before concluding" },
    { name: "Forensics", role: "reconstructs the timeline and the attack path" },
    { name: "Red", role: "autonomous penetration test — tries every exploit, blind" },
  ];
  return (
    <div className="animate-rise max-w-3xl mx-auto pt-14">
      <div className="label">about the project</div>
      <h1 className="display text-5xl md:text-6xl mt-4">An agent that<br /><span className="grad-text">investigates blind.</span></h1>
      <p className="text-sub text-lg mt-6 leading-relaxed">
        CyberArena is a multi-agent AI framework for industrial control system (ICS / OT) security. It pairs a
        realistic factory — with known, toggleable weaknesses — against a team of autonomous agents that attack it,
        investigate the aftermath, and explain what happened in plain language, mapped to MITRE ATT&CK for ICS.
      </p>

      <div className="grid sm:grid-cols-2 gap-4 mt-10">
        {facts.map((f) => (
          <div key={f.k} className="card p-5">
            <div className="label text-iris">{f.k}</div>
            <p className="text-sm text-sub mt-2 leading-relaxed">{f.v}</p>
          </div>
        ))}
      </div>

      <div className="label text-faint mt-12 mb-3">the agents</div>
      <div className="card divide-y divide-line">
        {agents.map((a) => (
          <div key={a.name} className="flex items-start gap-4 px-5 py-3.5">
            <Avatar agent={a.name === "Red" ? "System" : a.name} sm />
            <div>
              <div className="font-medium text-sm">{a.name}</div>
              <div className="text-sm text-sub">{a.role}</div>
            </div>
          </div>
        ))}
      </div>

      <div className="card p-5 mt-6">
        <div className="label text-iris">why it matters</div>
        <p className="text-sm text-sub mt-2 leading-relaxed">
          In a real SOC, detection raises an alert and a human does the slow, blind work of deciding whether it is a
          genuine compromise or authorised maintenance. CyberArena automates that reasoning — transparently and
          auditably — so the hard part of OT incident response is faster without ever taking a human out of the loop.
        </p>
      </div>

      <div className="mt-10"><button className="btn-soft px-5 h-11" onClick={onBack}>← Back</button></div>
      <p className="text-center text-xs text-faint mt-10">CyberArena · an academic project · RVCE</p>
    </div>
  );
}
