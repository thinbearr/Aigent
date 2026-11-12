import React from "react";

export const AGENTS: Record<string, { color: string; glyph: string; name: string }> = {
  Orchestrator: { color: "#deebc8", glyph: "◈", name: "Orchestrator" },
  Blue: { color: "#6bb6ff", glyph: "✦", name: "Blue · evidence" },
  Critic: { color: "#f0b44a", glyph: "⟁", name: "Critic · challenge" },
  Forensics: { color: "#5fd39a", glyph: "◆", name: "Forensics · timeline" },
  System: { color: "#9a9a9c", glyph: "•", name: "System" },
  "Report writer": { color: "#cbdfaa", glyph: "✎", name: "Report" },
};

export function Avatar({ agent, sm }: { agent: string; sm?: boolean }) {
  const a = AGENTS[agent] || AGENTS.System;
  const s = sm ? "w-6 h-6 text-[11px]" : "w-9 h-9 text-sm";
  return (
    <div className={`${s} rounded-xl grid place-items-center font-bold shrink-0`}
      style={{ background: `${a.color}18`, color: a.color, boxShadow: `inset 0 0 0 1px ${a.color}30` }}>
      {a.glyph}
    </div>
  );
}

// radial confidence dial
export function Dial({ value, incident }: { value: number; incident: boolean }) {
  const r = 52, c = 2 * Math.PI * r, pct = Math.max(0, Math.min(1, value));
  const col = incident ? "#f2537a" : "#5fd39a";
  return (
    <div className="relative w-[136px] h-[136px]">
      <svg viewBox="0 0 136 136" className="w-full h-full -rotate-90">
        <circle cx="68" cy="68" r={r} fill="none" stroke="#272729" strokeWidth="11" />
        <circle cx="68" cy="68" r={r} fill="none" stroke={col} strokeWidth="11" strokeLinecap="round"
          strokeDasharray={c} strokeDashoffset={c * (1 - pct)} style={{ transition: "stroke-dashoffset 1s cubic-bezier(.2,.7,.2,1)" }} />
      </svg>
      <div className="absolute inset-0 grid place-items-center text-center">
        <div>
          <div className="text-3xl font-bold tabular-nums" style={{ color: col }}>{Math.round(pct * 100)}<span className="text-lg">%</span></div>
          <div className="label mt-0.5">confidence</div>
        </div>
      </div>
    </div>
  );
}

export function Chip({ tone, children }: { tone: string; children: React.ReactNode }) {
  const m: Record<string, string> = {
    iris: "bg-iris/10 text-iris", mint: "bg-mint/10 text-mint", amber: "bg-amber/10 text-amber",
    rose: "bg-rose/10 text-rose", sky: "bg-sky/10 text-sky", slate: "bg-white/[0.07] text-sub",
  };
  return <span className={`chip font-mono text-[10px] uppercase tracking-wider ${m[tone] || m.slate}`}>{children}</span>;
}

export function Weight({ w }: { w: number }) {
  const pos = w >= 0;
  return <span className={`mono text-xs font-semibold px-1.5 py-0.5 rounded ${pos ? "bg-rose/10 text-rose" : "bg-mint/10 text-mint"}`}>{pos ? "+" : ""}{w.toFixed(1)}</span>;
}
