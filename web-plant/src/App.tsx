import { useEffect, useState } from "react";
import { authApi, getToken, setToken, dev, useLive } from "./api";
import { Dot, useToast } from "./kit";
import Operations from "./Operations";
import RangeControl from "./RangeControl";

const DEMO = [["p.nair", "Oper#2025p", "Operator"], ["s.iyer", "Eng#2025s", "Engineer"], ["r.mehta", "Super#2025r", "Supervisor"], ["m.rao", "Admin#2025m", "IT Admin"]];

export default function App() {
  const [user, setUser] = useState<any>(null);
  const [ready, setReady] = useState(false);
  const [tab, setTab] = useState<"ops" | "range">("ops");
  useEffect(() => { if (!getToken()) { setReady(true); return; } authApi.me().then(setUser).catch(() => setToken(null)).finally(() => setReady(true)); }, []);
  if (!ready) return null;
  if (!user) return <Login onIn={setUser} />;
  return (
    <div className="h-screen flex flex-col">
      <ShellBar user={user} onOut={() => { setToken(null); setUser(null); }} tab={tab} setTab={setTab} />
      <main className="flex-1 overflow-y-auto">
        <div className="max-w-[1400px] mx-auto p-5">
          {tab === "ops" ? <Operations role={user.role} /> : <RangeControl />}
        </div>
      </main>
    </div>
  );
}

function ShellBar({ user, onOut, tab, setTab }: any) {
  const st = useLive<any>(() => dev.get("/dev/status").catch(() => null), 4000);
  return (
    <header className="bg-shell text-white shrink-0">
      <div className="h-12 flex items-center px-4 gap-3">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded bg-white/15 grid place-items-center font-bold text-sm">K</div>
          <span className="font-semibold">Kaveri Process Industries</span>
          <span className="text-white/50 text-sm hidden sm:inline">· Plant Control</span>
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
        {[["ops", "Operations"], ["range", "Range Control"]].map(([k, l]) => (
          <button key={k} onClick={() => setTab(k)}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${tab === k ? "border-white text-white" : "border-transparent text-white/60 hover:text-white/90"}`}>{l}</button>
        ))}
      </div>
    </header>
  );
}

function Login({ onIn }: { onIn: (u: any) => void }) {
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
      <div className="hidden lg:flex flex-col justify-between bg-shell text-white p-12">
        <div className="flex items-center gap-2"><div className="w-9 h-9 rounded bg-white/15 grid place-items-center font-bold">K</div>
          <span className="font-semibold text-lg">Kaveri Process Industries</span></div>
        <div>
          <div className="text-white/60 text-sm font-medium">S/4 Integrated Operations</div>
          <h1 className="text-4xl font-bold mt-3 leading-tight">Plant control<br />& process operations.</h1>
          <p className="text-white/70 mt-4 max-w-md">SCADA control and the security test range for Line 2 beverage filling.
            This is the simulated target plant — where known fault and attack conditions are configured.</p>
        </div>
        <div className="text-xs text-white/50">Sandboxed simulation · deliberately includes known weaknesses · not a live plant.</div>
      </div>
      <div className="flex items-center justify-center p-8 bg-bg">
        <div className="w-full max-w-sm">
          <h2 className="text-xl font-semibold">Sign in</h2>
          <p className="sub mt-1">Operator / engineering credentials.</p>
          <div className="mt-5 space-y-3">
            <div><label className="lbl">Username</label><input className="input" value={u} onChange={e => setU(e.target.value)} /></div>
            <div><label className="lbl">Password</label><input className="input" type="password" value={p} onChange={e => setP(e.target.value)} onKeyDown={e => e.key === "Enter" && go()} /></div>
            <button className="btn-primary w-full justify-center" disabled={busy} onClick={go}>{busy ? "Signing in…" : "Sign in"}</button>
          </div>
          <div className="mt-6 pt-4 border-t border-line">
            <div className="lbl">Demo accounts</div>
            <div className="flex flex-wrap gap-1.5">
              {DEMO.map(([id, pw, role]) => <button key={id} onClick={() => { setU(id); setP(pw); }}
                className="text-xs px-2 py-1 rounded border border-line2 bg-white hover:border-brand text-sub">{role}</button>)}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
