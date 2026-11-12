# Two sites, two backends

Two independent products that interact only over HTTP. The plant is a disposable
simulation; the agent is the actual deliverable (autonomous investigation). Swap the
plant for a real log/ticket source and the agent is unchanged.

```
  PLANT  (simulation target)                          AGENT  (the product)
  ┌─────────────────────────────┐                     ┌──────────────────────────────┐
  │ plant-api                    │   HTTP, read-only   │ agent-api                    │
  │  :8000  operator + /evidence │◀────────────────────│  :8200  /agent/investigate   │
  │  :8100  dev / range control  │  GET /evidence/*     │   pulls events + tickets,    │
  │  :5020  Modbus/TCP           │  (evidence token)    │   runs Blue→Critic→Forensics │
  │                              │                      │   knows NO ground truth      │
  │ plant-web  :5191 (SAP style) │                      │ agent-web  :5192 (light/cool)│
  └─────────────────────────────┘                     └──────────────────────────────┘
```

- The agent **never shares the plant's database**. It calls `GET /evidence/events`
  and `GET /evidence/tickets` on the plant, exactly what a SOC analyst would have.
- It never sees the breach-point flags or the Case/ground-truth table.
- The plant's **Range Control** (`:5191` → Range Control tab) is where *you* set the
  known conditions: breach points, attack/maintenance scenarios, faults.
- The agent's console (`:5192`) pulls that evidence and decides, showing its full
  reasoning trace, the alternatives the Critic tested, timeline, path and MITRE.

## Run locally (no Docker)

```bash
./run.sh setup
```
Then four terminals:
```bash
./run.sh plant       # plant backend  :8000 / :8100 / :5020
```
```bash
./run.sh agent       # agent backend  :8200  (PLANT_URL=http://localhost:8000)
```
```bash
./run.sh plant-ui    # SAP plant console     http://localhost:5191
```
```bash
./run.sh agent-ui    # investigation console http://localhost:5192
```

## Run as containers

```bash
docker compose -f docker-compose.sites.yml up --build
```
Four containers on one network: `plant-api`, `agent-api` (with `PLANT_URL=http://plant-api:8000`),
`plant-web` (:5191), `agent-web` (:5192).

## The loop

1. On the **Plant** (`:5191` → Range Control): flip breach points / run a scenario / inject a fault.
2. On the **Agent** (`:5192`): press **Run investigation**. It pulls the evidence, investigates
   blind, and returns a verdict with confidence, evidence, the Critic's rejected alternatives,
   timeline, attack path, MITRE and suggested actions.
3. Compare the verdict with what you actually set — the agent was never told.

The agent backend's own API: `GET /agent/health`, `GET /agent/plant` (is the plant reachable +
what it sees), `POST /agent/investigate {critic, since_id}`, `POST /agent/redteam`.

## Agent-facing plant endpoints consumed by the agent

| Endpoint | Used by | Notes |
|---|---|---|
| `GET /evidence/events?since_id=&limit=` | Blue / Forensics / Critic | Paginated; agent loops until page < 2000 |
| `GET /evidence/tickets` | Critic | Change-ticket records for authorisation + scope checks |
| `GET /evidence/sources` | `GET /agent/plant` health check | Event counts by source |
| `GET /evidence/health` | `GET /agent/plant` health check | Live process state |
| `GET /attack/techniques` | Red agent | Lists all exploitable techniques |
| `POST /attack/attempt {"technique": id}` | Red agent | Attempts one technique; returns success/blocked/failed |
