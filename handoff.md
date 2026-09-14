# Handoff — Chartering_Model session (2026-09-14)

## How to run
```powershell
$env:Path += ";$env:LOCALAPPDATA\Programs\DockerDesktop\resources\bin"  # MS Store Docker path
cd C:\Users\LENOVO\Desktop\Chartering_Model
docker compose up --build -d
```
- Dashboard: http://localhost:3000 · API: http://localhost:8000 · API docs: `/docs`
- Docker Desktop 4.90.0 (MS Store install) + Compose v5.5.1. Backend needs the PATH line above until sign-out/in.
- Secrets live in `backend/.env` (gitignored). Keys configured: EIA, FRED, AISStream, VesselAPI. Dead Marinesia key removed.

## API keys status
| Key | Status |
|---|---|
| EIA (`EIA_KEY`) | Working — bunker live |
| FRED (`FRED_KEY`) | Working — commodities live |
| AISStream (`AISSTREAM_KEY`) | Working — live positions/congestion, worker running |
| yfinance (keyless) | Working — freight live (2,592 rows, added to requirements) |
| VesselAPI (`VESSELAPI_KEY`) | Working — 96-vessel real fleet synced |
| Marinesia | Key rejected (403) — removed from `.env`; its retry loop stalled boots 10+ min |

## Code changes (backend)
- `optimization/optimizer.py`
  - Evaluates **all** feasible vessel×port combos on cost+risk (was `feasible_vessels[0]` only); per-port congestion map; full-congestion port scoring on winner.
  - `OptimizationResult.vessel_options`: ranked best-contract-per-combo shortlist.
  - Winner **constrained to requested destination**; honest `NO_FEASIBLE_SOLUTION` w/ reason otherwise.
  - `required_voyages` honored: options with fewer voyages filtered out (largest fallback).
  - Spot leg priced at user's `current_freight_rate`; contracts at 50/50 user-rate/forecast blend.
  - Program-basis savings (`N×spot − contract`); headline savings read off winner.
  - New optional `as_of` param (defaults today; powers timing simulation).
- `optimization/feasibility.py` — inclusive laycan-overlap day counting (single-day overlaps/laycans score correctly).
- `optimization/timing.py` (new) — `TimingAdvisor`: re-runs optimizer per wait date (0/7/14/30/45/60), fixed laycan, forecast-curve rates, horizon-decayed confidence, GO_NOW/WAIT/NO_FEASIBLE_WINDOW verdict + assumptions.
- `data/sync_service.py` — freight `LIKE` query via `text()` + bound param (raw `%` crashed every sync under pandas 2.2 + SQLAlchemy 2.0).
- `data/connectors/freight_stooq.py` — BDI cache 20h → 6h.
- `backend/requirements.txt` — added `yfinance>=0.40`.
- `main.py`
  - `POST /api/timing` (new) + `TimingRequest` model. Total endpoints: 17 (16 `/api/` + root).
  - `/api/optimize` response adds `vessel_options`; skips Recommendation insert when no vessel; resolves real `port_id` by name (was hardcoded `0` → FK 500s).
  - `/api/feasibility` adds `port_id` per row + `unique_feasible_vessels`/`total_vessels` summary.
  - `/api/contracts` normalizes NULL→null (NaN broke JSON).

## Code changes (frontend)
- `VesselComparison.jsx` — unique row keys; "Vessels × Ports" labeling + unique-vessel count; RECOMMENDED badge = Decision winner (was row 0); port bars use primary at full/45% opacity (was invisible `#e2e8f0` on `#f1f5f9`).
- `ExecutiveDecision.jsx` — "Top Vessel × Port Alternatives" section from `vessel_options`.
- `Timing.jsx` (new) + `App.jsx` wiring — Timing tab: verdict banner, cost-by-date table, reasoning, assumptions. Uses last Decision params.

## Docker / compose changes
- `docker-compose.yml` — backend loads `backend/.env` via `env_file`; backend command is uvicorn-only (old unconditional re-seed crashed restarts with duplicate-key errors).
- DB one-offs (postgres): vessel availability windows shifted to cover 2026-08 → 2027-08; deleted 20 synthetic `MV …` demo vessels + 10 stale recommendations after real fleet sync (96 vessels).

## Data state (postgres)
- Freight: 70,144 synthetic baseline (2023–25, by design) + live BDRY rows from 2026-05-18 (live wins on overlap).
- Bunker/commodities/congestion: live. Fleet: 96 real VesselAPI ships.

## Known limitations / next steps
- Marinesia key invalid — replace or drop fallback; VesselAPI cache is 24h.
- `risk_engine` defines `market_weight` but never uses it in the overall score.
- `docker-compose.yml` still has obsolete `version:` key (warning only).
- No automated test suite — verification was via throwaway probes in `%LOCALAPPDATA%\Temp\opencode\probe_*.py`.
