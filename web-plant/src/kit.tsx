import React, { createContext, useCallback, useContext, useState } from "react";

export function Chip({ tone, children }: { tone: string; children: React.ReactNode }) {
  const m: Record<string, string> = {
    good: "bg-green-100 text-good", warn: "bg-orange-100 text-warn", bad: "bg-red-100 text-bad",
    crit: "bg-purple-100 text-crit", info: "bg-blue-100 text-brand", neutral: "bg-gray-100 text-sub",
  };
  return <span className={`chip ${m[tone] || m.neutral}`}>{children}</span>;
}
export function Dot({ tone }: { tone: string }) {
  const c: Record<string, string> = { good: "#107e3e", warn: "#e9730c", bad: "#bb0000", crit: "#6c2d91", info: "#0a6ed1", off: "#b0b4b8" };
  return <span className="inline-block w-2.5 h-2.5 rounded-full" style={{ background: c[tone] || c.off }} />;
}
const TC = createContext<(t: string, k?: "ok" | "err" | "info") => void>(() => {});
export const useToast = () => useContext(TC);
export function Toasts({ children }: { children: React.ReactNode }) {
  const [it, set] = useState<{ id: number; t: string; k: string }[]>([]);
  const push = useCallback((t: string, k = "info") => { const id = Date.now() + Math.random(); set(x => [...x, { id, t, k }]); setTimeout(() => set(x => x.filter(y => y.id !== id)), 3600); }, []);
  return <TC.Provider value={push}>{children}
    <div className="fixed bottom-4 right-4 z-50 space-y-2 w-80">
      {it.map(x => <div key={x.id} className="tile shadow-pop px-4 py-3 text-sm flex items-center gap-2 border-l-4"
        style={{ borderColor: x.k === "err" ? "#bb0000" : x.k === "ok" ? "#107e3e" : "#0a6ed1" }}>
        <Dot tone={x.k === "err" ? "bad" : x.k === "ok" ? "good" : "info"} />{x.t}</div>)}
    </div></TC.Provider>;
}
export function Modal({ open, onClose, title, children, wide }: { open: boolean; onClose: () => void; title: string; children: React.ReactNode; wide?: boolean }) {
  if (!open) return null;
  return <div className="fixed inset-0 z-40 bg-black/30 flex items-center justify-center p-4" onClick={onClose}>
    <div className={`tile ${wide ? "max-w-3xl" : "max-w-md"} w-full max-h-[85vh] overflow-auto`} onClick={e => e.stopPropagation()}>
      <div className="tile-h sticky top-0 bg-tile"><span className="tile-t">{title}</span>
        <button className="ml-auto text-sub hover:text-ink" onClick={onClose}>✕</button></div>
      <div className="p-4">{children}</div></div></div>;
}
