const TOK = "plant_token", DTOK = "plant_devtoken";
export const getToken = () => localStorage.getItem(TOK) || "";
export const setToken = (t: string | null) => t ? localStorage.setItem(TOK, t) : localStorage.removeItem(TOK);
export const getDevToken = () => localStorage.getItem(DTOK) || "arena-dev-token";
export const setDevToken = (t: string) => localStorage.setItem(DTOK, t);

async function req(path: string, opts: RequestInit, headers: Record<string, string>) {
  const res = await fetch(path, { ...opts, headers: { "content-type": "application/json", ...headers } });
  if (!res.ok) { let m = `${res.status}`; try { m = (await res.json()).detail || m; } catch {} throw new Error(typeof m === "string" ? m : JSON.stringify(m)); }
  if (res.status === 204) return null;
  return res.json();
}
const bear = (): Record<string, string> => { const t = getToken(); return t ? { authorization: `Bearer ${t}` } : {}; };
export const api = {
  get: (p: string) => req(p, {}, bear()),
  post: (p: string, b?: any) => req(p, { method: "POST", body: JSON.stringify(b ?? {}) }, bear()),
};
export const dev = {
  get: (p: string) => req(p, {}, { "x-dev-token": getDevToken() }),
  post: (p: string, b?: any) => req(p, { method: "POST", body: JSON.stringify(b ?? {}) }, { "x-dev-token": getDevToken() }),
};
export const authApi = {
  login: (username: string, password: string, via: string) =>
    req("/api/auth/login", { method: "POST", body: JSON.stringify({ username, password, via }) }, {}),
  me: () => api.get("/api/auth/me"),
};

import { useCallback, useEffect, useRef, useState } from "react";
export function useLive<T>(fn: () => Promise<T>, ms = 1500, deps: any[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const ref = useRef(fn); ref.current = fn;
  const reload = useCallback(async () => { try { setData(await ref.current()); setErr(null); } catch (e: any) { setErr(e.message); } }, []);
  useEffect(() => {
    let on = true; const t = async () => { if (on) await reload(); }; t();
    const id = ms > 0 ? setInterval(t, ms) : 0; return () => { on = false; if (id) clearInterval(id); };
    // eslint-disable-next-line
  }, deps);
  return { data, err, reload };
}
