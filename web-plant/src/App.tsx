import { useEffect, useState } from "react";
import { authApi, getToken, setToken, dev, useLive } from "./api";
import { Dot, useToast } from "./kit";
import Operations from "./Operations";
import RangeControl from "./RangeControl";

const DEMO = [["p.nair", "Oper#2025p", "Operator"], ["s.iyer", "Eng#2025s", "Engineer"], ["r.mehta", "Super#2025r", "Supervisor"], ["m.rao", "Admin#2025m", "IT Admin"]];

export default function App() {
  const [user, setUser] = useState<any>(null);
  const [ready, setReady] = useState(false);
  const [tab, setTab] = useState<"ops" | "range" | "about">("ops");
  const [pre, setPre] = useState<"landing" | "login" | "about">("landing");
  useEffect(() => { if (!getToken()) { setReady(true); return; } authApi.me().then(setUser).catch(() => setToken(null)).finally(() => setReady(true)); }, []);
  if (!ready) return null;
  if (!user) {
    if (pre === "login") return <Login onIn={setUser} onAbout={() => setPre("about")} onBack={() => setPre("landing")} />;
    if (pre === "about") return <About onBack={() => setPre("landing")} onEnter={() => setPre("login")} />;
    return <Landing onEnter={() => setPre("login")} onAbout={() => setPre("about")} />;
  }
  return (
    <div className="h-screen flex flex-col">
      <ShellBar user={user} onOut={() => { setToken(null); setUser(null); setPre("landing"); }} tab={tab} setTab={setTab} />
      <main className="flex-1 overflow-y-auto">
        <div className="max-w-[1400px] mx-auto p-5">
          {tab === "ops" ? <Operations role={user.role} /> : tab === "range" ? <RangeControl /> : <About embedded />}
        </div>
      </main>
    </div>
  );
}

function TopNav({ onAbout, onEnter, active }: { onAbout?: () => void; onEnter?: () => void; active?: string }) {
  return (
    <header className="h-16 flex items-center px-6 md:px-10 border-b border-line">
      <div className="flex items-center gap-2.5">
        <div className="w-8 h-8 rounded bg-ink text-cream grid place-items-center font-serif font-medium text-sm">K</div>
        <span className="font-serif text-[17px] tracking-tight">Kaveri Process Industries</span>
      </div>
      <nav className="ml-auto flex items-center gap-1.5">
        <button onClick={onAbout} className={`px-3.5 h-9 rounded-lg text-sm ${active === "about" ? "text-ink font-medium" : "text-sub hover:text-ink"}`}>About</button>
        <button onClick={onEnter} className="btn-primary h-9">Sign in →</button>
      </nav>
    </header>
  );
}

function Landing({ onEnter, onAbout }: { onEnter: () => void; onAbout: () => void }) {
  const stats = [
    ["11", "breach points", "known, toggleable weaknesses from L4 to L0"],
    ["L4→L0", "Purdue levels", "enterprise, operations, control and process"],
    ["ATT&CK", "for ICS", "every scenario mapped to MITRE techniques"],
  ];
  return (
    <div className="min-h-screen flex flex-col">
      <TopNav onAbout={onAbout} onEnter={onEnter} />
      <section className="flex-1 flex items-center">
        <div className="max-w-[1100px] mx-auto px-6 md:px-10 w-full py-16">
          <div className="max-w-3xl">
            <div className="eyebrow">S/4 Integrated Operations · simulated target plant</div>
            <h1 className="display text-5xl md:text-7xl mt-5 leading-[1.04]">Plant control,<br />turned into <span className="italic text-accent">process truth</span>.</h1>
            <p className="text-sub mt-6 text-lg max-w-xl leading-relaxed">A faithful SCADA plant for Line 2 beverage filling — with deliberate, switchable security weaknesses. Configure the conditions; let the investigation agent discover them.</p>
            <div className="flex flex-wrap gap-3 mt-8">
              <button className="btn-primary h-12 px-6 text-base" onClick={onEnter}>Enter the console →</button>
              <button className="btn-emph h-12 px-6 text-base" onClick={onAbout}>About the project</button>
            </div>
          </div>
          <div className="grid sm:grid-cols-3 gap-4 mt-16">
            {stats.map(([n, l, d]) => (
              <div key={l} className="tile p-6">
                <div className="objnum text-ink">{n}</div>
                <div className="font-mono text-[11px] uppercase tracking-[0.12em] text-accent mt-3">{l}</div>
                <div className="sub mt-2 leading-relaxed">{d}</div>
              </div>
            ))}
          </div>
        </div>
      </section>
      <footer className="border-t border-line py-5 px-6 md:px-10">
        <div className="max-w-[1100px] mx-auto font-mono text-[10.5px] uppercase tracking-[0.12em] text-sub">
          Sandboxed simulation · deliberate weaknesses · not a live plant
        </div>
      </footer>
    </div>
  );
}

function About({ onBack, onEnter, embedded }: { onBack?: () => void; onEnter?: () => void; embedded?: boolean }) {
  const facts = [
    ["A faithful plant", "SCADA/HMI control of a real beverage line — tanks, heater, conveyor, pumps, a PLC and a safety system — running live physics, not a mock-up."],
    ["Switchable weaknesses", "Eleven breach points from the enterprise network down to the process can be turned on or off, each mapped to a real ICS attack technique."],
    ["Normal traffic, always on", "Simulated staff keep working — logins, alarm acks, report views — so any attack is mixed into realistic background noise."],
    ["Ground truth, kept private", "Range Control configures the conditions; the investigation agent never sees them. It must discover what is wrong from evidence alone."],
  ];
  const layers = [
    ["L4", "Enterprise", "ERP, remote portal, file shares"],
    ["L3", "Operations", "historian, engineering workstation"],
    ["L2", "Supervisory", "SCADA / HMI console"],
    ["L1", "Control", "PLC, safety-instrumented system"],
    ["L0", "Process", "tanks, heater, conveyor, valves"],
  ];
  const Body = (
    <div className="max-w-3xl mx-auto">
      <div className="eyebrow">About the target plant</div>
      <h1 className="display text-4xl md:text-6xl mt-4 leading-[1.05]">A plant built to<br />be <span className="italic text-accent">broken into</span>.</h1>
      <p className="text-sub text-lg mt-6 leading-relaxed">
        This is the simulated factory at the heart of CyberArena — a professional-looking plant control system with
        known, deliberate security flaws. It exists so an autonomous investigation agent can be tested against
        realistic, repeatable incidents, mapped to MITRE ATT&CK for ICS.
      </p>

      <div className="grid sm:grid-cols-2 gap-4 mt-10">
        {facts.map(([k, v]) => (
          <div key={k} className="tile p-5">
            <div className="font-mono text-[11px] uppercase tracking-[0.12em] text-accent">{k}</div>
            <p className="sub mt-2 leading-relaxed text-[13px]">{v}</p>
          </div>
        ))}
      </div>

      <div className="eyebrow mt-14 mb-3">The Purdue model</div>
      <div className="tile divide-y divide-line">
        {layers.map(([lv, name, d]) => (
          <div key={lv} className="flex items-center gap-4 px-5 py-3.5">
            <span className="font-mono text-sm text-accent w-8">{lv}</span>
            <span className="font-medium text-sm w-28">{name}</span>
            <span className="sub">{d}</span>
          </div>
        ))}
      </div>

      <div className="tile p-6 mt-8">
        <div className="eyebrow">Two independent systems</div>
        <p className="sub mt-2 leading-relaxed">
          The plant and the investigation agent are separate services that only talk over the network. The plant is a
          disposable simulation; the agent is the product. Swap the plant for a real log source and the agent is
          unchanged — which is the whole point.
        </p>
      </div>

      {!embedded && (
        <div className="flex gap-3 mt-10">
          {onBack && <button className="btn-emph h-11 px-5" onClick={onBack}>← Back</button>}
          {onEnter && <button className="btn-primary h-11 px-5" onClick={onEnter}>Enter the console →</button>}
        </div>
      )}
      {!embedded && <p className="font-mono text-[10.5px] uppercase tracking-[0.12em] text-sub mt-12">CyberArena · an academic project · RVCE</p>}
    </div>
  );
  if (embedded) return <div className="animate-none">{Body}</div>;
  return (
    <div className="min-h-screen flex flex-col">
      <TopNav onAbout={onBack} onEnter={onEnter} active="about" />
      <section className="flex-1 py-14 px-6">{Body}</section>
    </div>
  );
}

function ShellBar({ user, onOut, tab, setTab }: any) {
  const st = useLive<any>(() => dev.get("/dev/status").catch(() => null), 4000);
  return (
    <header className="bg-shell text-white shrink-0">
      <div className="h-12 flex items-center px-4 gap-3">
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded bg-cream text-ink grid place-items-center font-serif font-medium text-sm">K</div>
          <span className="font-serif text-[17px] tracking-tight">Kaveri Process Industries</span>
          <span className="font-mono text-[10px] uppercase tracking-[0.15em] text-white/40 hidden sm:inline ml-1">Plant Control</span>
        </div>
        <div className="ml-auto flex items-center gap-4 text-sm">
          <span className="hidden md:flex items-center gap-1.5 text-white/80">
            <Dot tone={st.data?.sis_tripped ? "bad" : "good"} />{st.data?.sis_tripped ? "SIS Tripped" : "Process nominal"}</span>
          <span className="text-white/60 hidden lg:inline">Plant 1000 · Bengaluru · Line 2</span>
          <div className="flex items-center gap-2 pl-3 border-l border-white/15">
            <div className="w-7 h-7 rounded-full bg-white/20 grid place-items-center text-xs font-semibold">
              {user.full_name?.split(" ").map((s: string) => s[0]).slice(0, 2).join("")}</div>
            <span className="text-white/80 text-xs hidden sm:inline">{user.username}</span>
            <button className="text-white/70 hover:text-white text-xs ml-1" onClick={onOut}>Sign out</button>
          </div>
        </div>
      </div>
      <div className="px-4 flex gap-1">
        {[["ops", "Operations"], ["range", "Range Control"], ["about", "About"]].map(([k, l]) => (
          <button key={k} onClick={() => setTab(k)}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${tab === k ? "border-white text-white" : "border-transparent text-white/60 hover:text-white/90"}`}>{l}</button>
        ))}
      </div>
    </header>
  );
}

function Login({ onIn, onAbout, onBack }: { onIn: (u: any) => void; onAbout: () => void; onBack: () => void }) {
  const toast = useToast();
  const [u, setU] = useState("p.nair"); const [p, setP] = useState("Oper#2025p");
  const [busy, setBusy] = useState(false);
  const go = async () => {
    setBusy(true);
    try { const r = await authApi.login(u, p, "corp"); setToken(r.token);
      if (r.mfa_required) { toast("This account needs MFA; use a non-remote account for the demo", "err"); setToken(null); }
      else onIn(await authApi.me());
    } catch (e: any) { toast(e.message, "err"); setToken(null); } finally { setBusy(false); }
  };
  return (
    <div className="min-h-screen grid lg:grid-cols-2">
      <div className="hidden lg:flex flex-col justify-between bg-shell text-white p-14 relative overflow-hidden">
        <button className="flex items-center gap-2.5 relative z-10 text-left" onClick={onBack}>
          <div className="w-9 h-9 rounded bg-cream text-ink grid place-items-center font-serif font-medium">K</div>
          <span className="font-serif text-lg tracking-tight">Kaveri Process Industries</span></button>
        <div className="relative z-10">
          <div className="eyebrow !text-accent2">S/4 Integrated Operations</div>
          <h1 className="display text-white text-5xl mt-5 leading-[1.06]">Plant control,<br />turned into <span className="italic text-accent2">process truth</span>.</h1>
          <p className="text-white/55 mt-6 max-w-md leading-relaxed">SCADA control and the security test range for Line 2 beverage filling —
            the simulated target plant where known fault and attack conditions are configured.</p>
          <button onClick={onAbout} className="font-mono text-[11px] uppercase tracking-[0.14em] text-accent2 hover:text-white mt-6 transition-colors">About the project →</button>
        </div>
        <div className="font-mono text-[10.5px] uppercase tracking-[0.12em] text-white/35 relative z-10">Sandboxed simulation · deliberate weaknesses · not a live plant</div>
        <div className="absolute -right-24 -bottom-24 w-96 h-96 rounded-full bg-accent/10 blur-3xl" />
      </div>
      <div className="flex items-center justify-center p-8 bg-bg">
        <div className="w-full max-w-sm">
          <div className="eyebrow mb-2">Access</div>
          <h2 className="display text-3xl">Sign in</h2>
          <p className="sub mt-1.5">Operator / engineering credentials.</p>
          <div className="mt-5 space-y-3">
            <div><label className="lbl">Username</label><input className="input" value={u} onChange={e => setU(e.target.value)} /></div>
            <div><label className="lbl">Password</label><input className="input" type="password" value={p} onChange={e => setP(e.target.value)} onKeyDown={e => e.key === "Enter" && go()} /></div>
            <button className="btn-primary w-full justify-center" disabled={busy} onClick={go}>{busy ? "Signing in…" : "Sign in"}</button>
          </div>
          <div className="mt-6 pt-4 border-t border-line">
            <div className="lbl">Demo accounts</div>
            <div className="flex flex-wrap gap-1.5">
              {DEMO.map(([id, pw, role]) => <button key={id} onClick={() => { setU(id); setP(pw); }}
                className="text-xs px-2 py-1 rounded border border-line2 bg-white hover:border-ink text-sub">{role}</button>)}
            </div>
          </div>
          <button onClick={onBack} className="sub mt-6 hover:text-ink lg:hidden">← Back to home</button>
        </div>
      </div>
    </div>
  );
}
