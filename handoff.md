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

---

# Update — 2026-09-20 (codebase-memory-mcp full index)

## 1. Project identity
- Path: `C:\Users\LENOVO\Desktop\Chartering_Model`
- Graph project: `C-Users-LENOVO-Desktop-Chartering_Model`
- Index mode: `full` + persistence `true`, status `ready`
- Artifact: `.codebase-memory/graph.db.zst` (untracked, commit to share)
- Log: `C:/Users/LENOVO/.cache/codebase-memory-mcp/logs/C-Users-LENOVO-Desktop-Chartering_Model-*.log`
- Counts: **468 nodes / 1576 edges** (was 467/1573 on first pass; +1 Route `/search/vessels` + HTTP_CALLS edge on re-read)

## 2. What codebase-memory-mcp is / is not
- Is: structural knowledge graph for agents — `search_graph`, `trace_path`, `get_code_snippet`, `query_graph`, `get_architecture`, `check_index_coverage`.
- Is not: has **no built-in UI**, no globe. Viewers in repo root were hand-built from graph output:
  - `codebase-memory-graph.html` (offline 3-column: folders → files → details)
  - `codebase-memory-globe.html` (offline canvas rotating globe, subset ~40 key nodes)
- Excluded by design (not errors): `.git/`, `frontend/dist`, `frontend/node_modules`, `backend/__pycache__`, `*/__pycache__`, `backend/data/.cache`, `*.db` (`maritime.db`, `runtime.db`), `backend/.env`, `opencode.json`. Parse-unusable: `nginx.conf` (read source directly).

## 3. Stack (verified)
- Backend: FastAPI 0.115.0, uvicorn 0.30.0, SQLAlchemy 2.0.35, psycopg2-binary 2.9.9, pandas 2.2.3, numpy 1.26.4, Prophet 1.1.5, XGBoost 2.1.1, scikit-learn 1.5.2, pydantic 2.9.2, requests, yfinance>=0.2.40, apscheduler>=3.10, python-dotenv, websockets>=12.0
- Frontend: React (Vite, `vite.config.js`), Recharts, `src/App.jsx`, `src/main.jsx`, 9 components in `src/components/`
- DB: postgres:16-alpine, db `maritime_chartering`, user/pass `postgres/postgres`, vol `pgdata`, healthcheck `pg_isready`
- Deploy: `docker-compose.yml` (3 services: db:5432, backend:8000 uvicorn-only, frontend:3000), `Dockerfile.backend`, `Dockerfile.frontend`, `nginx.conf`

## 4. File tree (60 entries, 49 files, 11 folders)
- `README.md`, `handoff.md`, `docker-compose.yml`, `nginx.conf`, `Dockerfile.backend`, `Dockerfile.frontend`, `opencode.json` (gitignored)
- `backend/`: `.env.example`, `REALTIME_DATA.md`, `requirements.txt`, `test_pipeline.py`, `main.py`
- `backend/api/__init__.py`
- `backend/data/`: `__init__.py`, `ingestion.py`, `preprocessing.py`, `realtime_fetcher.py`, `sync_service.py`
- `backend/data/connectors/` (8): `__init__.py`, `ais_worker.py`, `base.py`, `bunker_eia.py`, `commodities_fred.py`, `freight_stooq.py`, `vessels_marinesia.py`, `vessels_vesselapi.py`
- `backend/database/`: `__init__.py`, `models_db.py` (14 classes), `postgres.py` (`get_db`)
- `backend/models/`: `__init__.py`, `forecast_model.py` (`FreightForecaster`, `ForecastResult`)
- `backend/optimization/` (5): `__init__.py`, `cost_engine.py` (`CostEngine`, `CostBreakdown`), `feasibility.py` (`FeasibilityEngine`, `FeasibleVessel`), `optimizer.py` (`CharteringOptimizer`, `OptimizationResult`), `timing.py` (`TimingAdvisor`, `TimingVerdict`)
- `backend/risk/`: `__init__.py`, `risk_engine.py` (`RiskEngine`, `RiskScore`)
- `frontend/`: `index.html`, `vite.config.js`, `src/App.css`, `src/App.jsx`, `src/main.jsx`, `src/components/` (9): `ContractComparison.jsx`, `DataStatus.jsx`, `ExecutiveDecision.jsx`, `ForecastView.jsx`, `ScenarioSimulator.jsx`, `Skeleton.jsx` (7 skeletons: Sk/Decision/Forecast/Vessels/Contracts/Timing/Scenario), `Timing.jsx`, `VesselComparison.jsx`, `WhyPanel.jsx`
- Languages: Python 28 files, JavaScript 12, YAML 1, HTML 1, CSS 1

## 5. Routes (20 indexed, 18 real + 2 noise)
`GET /`, `GET /api/health`, `POST /api/forecast`, `POST /api/feasibility`, `POST /api/cost`, `POST /api/optimize`, `POST /api/scenario`, `POST /api/timing`, `GET /api/recommendation/{id}`, `POST /api/recommendation/{id}/action`, `GET /api/fleet-suggestion`, `GET /api/vessels`, `GET /api/ports`, `GET /api/contracts`, `GET /api/congestion`, `POST /api/sync`, `GET /api/data-status`, `POST /api/backtest` (+ noise: `/search/vessels`, `postgresql://...` connection string mis-tagged as route).
- Pydantic models in `main.py`: `ForecastRequest`, `FeasibilityRequest`, `CostRequest`, `OptimizationRequest`, `ScenarioRequest`, `TimingRequest`, `RecommendationAction` + `to_serializable()`.

## 6. DB schema (`models_db.py`, 14 mapped classes)
`Vessel`, `VesselClass` (enum), `Port`, `PortCongestion`, `Contract`, `ContractType` (enum), `CargoRequirement`, `FreightRate`, `CommodityPrice`, `BunkerPrice`, `Forecast`, `Recommendation`, `RecommendationAction` (enum), `SyncRun`. README says "9 tables" — stale; actual is 14.

## 7. Graph stats
- Labels: Function 132, Variable 63, File 49, Method 49, Module 42, Class 38, Section 32, Route 20, Package 16, EnvVar 12, Folder 11, Decorator 2, Branch 1, Project 1
- Edges: DEFINES 609, CALLS 420, USAGE 134, IMPORTS 87, WRITES 75, CONTAINS_FILE 49, DEFINES_METHOD 44, FILE_CHANGES_WITH 29, SEMANTICALLY_RELATED 27, DECORATES 25, HANDLES 18, DEPENDS_ON 16, CONFIGURES 13, SIMILAR_TO 13, CONTAINS_FOLDER 11, INHERITS 3, CALL_REFERENCE 1, HAS_BRANCH 1, HTTP_CALLS 1
- Hotspots (fan-in): `len` 26, `list.append` 25, `print` 22, `fetch_vessels_realtime` 9, `fetch_congestion_realtime` 9, `dict.get` 9, `fetch_bunker_realtime` 8, `to_serializable` 8, `fetch_freight_realtime` 7, `load_ports` 6. Note: `get_db` (16) seen in earlier snapshot, now outside top-10 after re-index — still critical.
- Boundaries: `main→data` 50 calls, `main→optimization` 13, `main→models` 11, `main→database` 18 (earlier snap).
- Layers: `main` entry (only outbound), `data`/`database`/`optimization`/`models` core, `src` internal.
- Clusters: backend optimize/assess_timing/run_scenario/fetch_* (cohesion ~0.59), backend optimize/get/calculate_risk/_parse_vessel/advise, frontend App/ExecutiveDecision/ScenarioSimulator/WhyPanel (cohesion 1.0), backend print/fetch_vessels/lifespan/http_get, etc.

## 8. Key call chains (sampled)
- `main.optimize → optimization/optimizer.optimize`; `main.assess_timing → optimization/timing.assess_timing`; `main.* → database/postgres.get_db`
- `connectors/base.http_get → cache_read/cache_write/_cache_path`; `vessels_marinesia.fetch_vessels → _fetch_vessels_from_area → _parse_vessel → _estimate_vessel_class + cache_read/write`
- `ais_worker._ais_consumer_loop → get_port_for_coord → is_in_bbox`; `start_ais_worker → print`
- `ingestion.generate_vessels/congestion/bunker/commodity/freight → list.append`

## 9. Git state @ 2026-09-20
- Log (last 13): `bd25b05 feat: replace spinners with skeleton loading placeholders` / `6c0a1a7 feat: dynamic fleet size (num_ships)...` / `e190c34 feat: optimizer overhaul, live-data fixes, timing advisor...` / `9494bb9 Use dynamic dates...` / `9baf2eb revert: restore previous CSS...` / `a955233 style: apply Oceanic Precision...` / `8c2501d feat: enterprise UI redesign + real vessel data...` / `1da8ced feat: redesign UI to light aesthetic...` / `45fa4ba Initial` / `fcbe716 Reconfigure to live data...` / `6489feb ...` / `5b2a0f0 Configure frontend API URL` / `46e145d Initial Commit`
- Dirty: `M frontend/src/App.jsx`, `M frontend/src/components/ForecastView.jsx`, `?? .codebase-memory/` (index artifact), `?? codebase-memory-graph.html`, `?? codebase-memory-globe.html` (viewers, decide to commit or gitignore)
- Branch: detached/unknown from graph `Branch` node — verify with `git branch --show-current` before committing.

## 10. Data + runtime notes (carryover + delta)
- Freight 70,144 synthetic (2023–25) + live BDRY from 2026-05-18; bunker/commodities/congestion live; fleet 96 VesselAPI ships; availability 2026-08→2027-08; 20 synthetic `MV…` + 10 stale recs deleted.
- Endpoints total now 18 real (17 claimed 09-14 + `/api/fleet-suggestion` confirmed in graph). Docs at `/docs`.
- Open issues: Marinesia 403 fallback, `market_weight` unused, `version:` obsolete key, no test suite, README schema count stale (9 vs 14), noise routes in index.

## 11. How to re-index / query
```powershell
# re-index after big changes
# index_repository(repo_path="C:\Users\LENOVO\Desktop\Chartering_Model", mode="full")
# search_graph(name_pattern=".*Optimizer.*"), trace_path(function_name="optimize", direction="both"), get_code_snippet(qualified_name="..."), query_graph Cypher, check_index_coverage for cited paths
```
