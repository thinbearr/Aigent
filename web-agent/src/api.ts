async function req(path: string, opts: RequestInit = {}) {
  const res = await fetch(path, { ...opts, headers: { "content-type": "application/json", ...(opts.headers || {}) } });
  if (!res.ok) { let m = `${res.status}`; try { m = (await res.json()).detail || m; } catch {} throw new Error(typeof m === "string" ? m : JSON.stringify(m)); }
  return res.json();
}
export const agent = {
  health: () => req("/agent/health"),
  plant: () => req("/agent/plant"),
  redteam: () => req("/agent/redteam", { method: "POST", body: "{}" }),
  investigate: (critic: boolean, since_id = 0) => req("/agent/investigate", { method: "POST", body: JSON.stringify({ critic, since_id }) }),
};

import { useCallback, useEffect, useRef, useState } from "react";
export function useLive<T>(fn: () => Promise<T>, ms = 4000) {
  const [data, setData] = useState<T | null>(null);
  const ref = useRef(fn); ref.current = fn;
  const reload = useCallback(async () => { try { setData(await ref.current()); } catch {} }, []);
  useEffect(() => { let on = true; const t = () => on && reload(); t(); const id = setInterval(t, ms); return () => { on = false; clearInterval(id); }; }, []);
  return { data, reload };
}
