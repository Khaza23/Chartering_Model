# Graph Report - Chartering_Model  (2026-10-10)

## Corpus Check
- 93 files · ~374,495 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 17 file(s) not represented in the graph (top: .log 5, (none) 2, .gcp 2)

## Summary
- 669 nodes · 1370 edges · 60 communities (27 shown, 33 thin omitted)
- Extraction: 95% EXTRACTED · 5% INFERRED · 0% AMBIGUOUS · INFERRED: 73 edges (avg confidence: 0.88)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- Frontend Dependencies
- Market Data Connectors
- Realtime Data Fetching
- Cost Feasibility Engines
- Synthetic Data Seeding
- Architecture Overview Diagram
- Live Sync Service
- External API Integration
- Lifecycle Sequence Diagrams
- Architecture Annotations Panel
- Lifecycle State Machine
- Optimization Pipeline Stages
- Dataflow Pipeline Stages
- Lifecycle Detailed States
- Optimize Request Sequence
- Freight Forecast Models
- AIS Worker Service
- Lifecycle Core States
- Decision Pipeline Features
- Architecture Components Light
- Architecture Components Dark
- Dataflow Stores Feeds
- Core System Components
- Frontend Cloud Build
- Sequence Participants Set
- Sequence Flow Light
- Sequence Flow Dark
- Docker Compose Services
- FRED Commodity Prices
- Architecture Diagram Singleton
- Compose Boundary Singleton
- Backend Network Boundary
- Decision Engine Singleton
- Archify Architecture Evidence
- Data Pipeline Diagram
- Pipeline Diagram Duplicate
- Dataflow Check Placeholder
- Chartering Pipeline Singleton
- Archify Dataflow Evidence
- Lifecycle Diagram Singleton
- Expired State Singleton
- Rejected State Singleton
- Revise State Singleton
- Lifecycle Root Singleton
- Archify Lifecycle Evidence
- Optimize Roundtrip Singleton
- Archify Sequence Evidence
- Optimization Pipeline Singleton
- No Solution Singleton
- Timing Advisor Singleton
- Archify Workflow Evidence
- What-If Simulator Singleton
- SAIL App Shell
- Decision Engine Title

## God Nodes (most connected - your core abstractions)
1. `CharteringOptimizer` - 24 edges
2. `optimize()` - 23 edges
3. `assess_timing()` - 21 edges
4. `fetch_congestion_realtime()` - 17 edges
5. `fetch_vessels_realtime()` - 17 edges
6. `fetch_freight_realtime()` - 16 edges
7. `fetch_bunker_realtime()` - 16 edges
8. `FreightForecaster` - 16 edges
9. `seed_database()` - 15 edges
10. `run_scenario()` - 15 edges

## Surprising Connections (you probably didn't know these)
- `Freight Rates via yfinance BDRY proxy` --shares_data_with--> `Freight Forecast Engine (Prophet + XGBoost Ensemble)`  [INFERRED]
  backend/REALTIME_DATA.md → README.md
- `Backend Python dependency stack` --references--> `Freight Forecast Engine (Prophet + XGBoost Ensemble)`  [INFERRED]
  backend/requirements.txt → README.md
- `Vessel Positions and Port Congestion via AISStream` --shares_data_with--> `Feasibility Engine (vessel/port filtering)`  [INFERRED]
  backend/REALTIME_DATA.md → README.md
- `Bunker Fuel Prices via EIA trend` --shares_data_with--> `Cost Engine (total voyage cost)`  [INFERRED]
  backend/REALTIME_DATA.md → README.md
- `sync_vessel_positions()` --uses--> `Vessel`  [INFERRED]
  backend/data/sync_service.py → backend/database/models_db.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Chartering decision pipeline Forecast to Optimization** — readme_freight_forecast_engine, readme_feasibility_engine, readme_cost_engine, readme_risk_engine, readme_optimization_engine [EXTRACTED 1.00]
- **Live data integration from APIs to frontend** — backend_realtime_data_freight_yfinance, backend_realtime_data_commodities_fred, backend_realtime_data_bunker_eia, backend_realtime_data_aisstream_congestion, backend_realtime_data_sync_service_flow, backend_realtime_data_realtime_fetcher [EXTRACTED 1.00]
- **Docker Compose db backend frontend stack** — docker_compose_db_service, docker_compose_backend_service, docker_compose_frontend_service [EXTRACTED 1.00]
- **Decision path engine chain** — docs_diagrams_architecture_fastapi, docs_diagrams_architecture_forecast_engine, docs_diagrams_architecture_optimization_engine [EXTRACTED 0.95]
- **Collection path into Postgres** — docs_diagrams_dataflow_market_feeds, docs_diagrams_dataflow_sync_service, docs_diagrams_dataflow_freight_rates [EXTRACTED 0.95]
- **Main recommendation lifecycle** — docs_diagrams_lifecycle_draft, docs_diagrams_lifecycle_recommended, docs_diagrams_lifecycle_closed [EXTRACTED 0.95]
- **Docker Compose deployment group** — docs_diagrams_architecture_react_dashboard, docs_diagrams_architecture_fastapi, docs_diagrams_architecture_postgresql [EXTRACTED 1.00]
- **Store stage data stores** — docs_diagrams_dataflow_freight_rates, docs_diagrams_dataflow_fleet_store, docs_diagrams_dataflow_bunker_commodity [EXTRACTED 1.00]
- **Process stage ensemble plus optimizer** — docs_diagrams_dataflow_forecast_ensemble, docs_diagrams_dataflow_cost_risk_optimizer, docs_diagrams_dataflow_dashboard [EXTRACTED 1.00]
- **Main lifecycle path Draft to Closed** — lifecycle_state_draft, lifecycle_state_analyzing, lifecycle_state_recommended [INFERRED 0.85]
- **Optimize request roundtrip flow** — sequence_actor_react_app, sequence_actor_fastapi, sequence_actor_optimizer [INFERRED 0.85]
- **Forecast to optimizer engine pipeline** — workflow_forecast_rates, workflow_feasibility_filter, workflow_spot_vs_contract [INFERRED 0.85]
- **sg-backend Cluster** — docs_diagrams_architecture_visual_check_2048x1320_dark_fastapi, docs_diagrams_architecture_visual_check_2048x1320_dark_optimization_engine, docs_diagrams_architecture_visual_check_2048x1320_dark_sync_service [EXTRACTED 1.00]
- **Docker Compose Stack** — docs_diagrams_architecture_visual_check_2048x1320_dark_react_dashboard, docs_diagrams_architecture_visual_check_2048x1320_dark_nginx, docs_diagrams_architecture_visual_check_2048x1320_dark_fastapi, docs_diagrams_architecture_visual_check_2048x1320_dark_postgresql, docs_diagrams_architecture_visual_check_2048x1320_dark_forecast_engine, docs_diagrams_architecture_visual_check_2048x1320_dark_optimization_engine, docs_diagrams_architecture_visual_check_2048x1320_dark_sync_service [EXTRACTED 1.00]
- **Docker Compose deployment boundary** — docs_diagrams_architecture_visual_check_2048x1320_light_react_dashboard, docs_diagrams_architecture_visual_check_2048x1320_light_nginx, docs_diagrams_architecture_visual_check_2048x1320_light_fastapi, docs_diagrams_architecture_visual_check_2048x1320_light_forecast_engine, docs_diagrams_architecture_visual_check_2048x1320_light_optimization_engine, docs_diagrams_architecture_visual_check_2048x1320_light_postgresql, docs_diagrams_architecture_visual_check_2048x1320_light_sync_service, docs_diagrams_architecture_visual_check_2048x1320_light_fleet_apis [EXTRACTED 1.00]
- **sg-backend FastAPI PostgreSQL boundary** — docs_diagrams_architecture_visual_check_2048x1320_light_fastapi, docs_diagrams_architecture_visual_check_2048x1320_light_optimization_engine, docs_diagrams_architecture_visual_check_2048x1320_light_postgresql [EXTRACTED 1.00]
- **Forecast optimizer Postgres engine chain** — docs_diagrams_architecture_visual_check_2048x1320_light_fastapi, docs_diagrams_architecture_visual_check_2048x1320_light_forecast_engine, docs_diagrams_architecture_visual_check_2048x1320_light_optimization_engine, docs_diagrams_architecture_visual_check_2048x1320_light_postgresql [INFERRED 0.85]
- **Chartering Data Pipeline (Sources → Ingest → Store → Process → Consume)** — docs_diagrams_dataflow_visual_check_2048x1320_dark_market_feeds, docs_diagrams_dataflow_visual_check_2048x1320_dark_fleet_feeds, docs_diagrams_dataflow_visual_check_2048x1320_dark_sync_service, docs_diagrams_dataflow_visual_check_2048x1320_dark_freight_rates, docs_diagrams_dataflow_visual_check_2048x1320_dark_fleet_store, docs_diagrams_dataflow_visual_check_2048x1320_dark_bunker_commodity, docs_diagrams_dataflow_visual_check_2048x1320_dark_forecast_ensemble, docs_diagrams_dataflow_visual_check_2048x1320_dark_cost_risk_optimizer, docs_diagrams_dataflow_visual_check_2048x1320_dark_dashboard, docs_diagrams_dataflow_visual_check_2048x1320_dark_recommendations [EXTRACTED 1.00]
- **Chartering Pipeline Stages** — docs_diagrams_dataflow_visual_check_2048x1320_light_sources_stage, docs_diagrams_dataflow_visual_check_2048x1320_light_ingest_stage, docs_diagrams_dataflow_visual_check_2048x1320_light_store_stage, docs_diagrams_dataflow_visual_check_2048x1320_light_process_stage, docs_diagrams_dataflow_visual_check_2048x1320_light_consume_stage [EXTRACTED 1.00]
- **Collection: sources land in Postgres via sync service** — docs_diagrams_dataflow_visual_check_2048x1320_light_market_feeds, docs_diagrams_dataflow_visual_check_2048x1320_light_fleet_feeds, docs_diagrams_dataflow_visual_check_2048x1320_light_sync_service [EXTRACTED 1.00]
- **Consumers: Dashboard reads recommendations plus forecast charts** — docs_diagrams_dataflow_visual_check_2048x1320_light_dashboard, docs_diagrams_dataflow_visual_check_2048x1320_light_recommendations, docs_diagrams_dataflow_visual_check_2048x1320_light_forecast_ensemble [EXTRACTED 1.00]
- **01 / Decision phases** — docs_diagrams_lifecycle_visual_check_1440x900_dark_draft, docs_diagrams_lifecycle_visual_check_1440x900_dark_analyzing, docs_diagrams_lifecycle_visual_check_1440x900_dark_recommended, docs_diagrams_lifecycle_visual_check_1440x900_dark_decided, docs_diagrams_lifecycle_visual_check_1440x900_dark_closed [EXTRACTED 1.00]
- **02 / Human waits + Recovery loop** — docs_diagrams_lifecycle_visual_check_1440x900_dark_needs_approval, docs_diagrams_lifecycle_visual_check_1440x900_dark_revise, docs_diagrams_lifecycle_visual_check_1440x900_dark_failed [EXTRACTED 1.00]
- **03 / Terminal exits** — docs_diagrams_lifecycle_visual_check_1440x900_dark_rejected, docs_diagrams_lifecycle_visual_check_1440x900_dark_expired [EXTRACTED 1.00]
- **Main lifecycle flow from Draft to Closed** — docs_diagrams_lifecycle_visual_check_2048x1320_dark_draft, docs_diagrams_lifecycle_visual_check_2048x1320_dark_analyzing, docs_diagrams_lifecycle_visual_check_2048x1320_dark_recommended, docs_diagrams_lifecycle_visual_check_2048x1320_dark_decided, docs_diagrams_lifecycle_visual_check_2048x1320_dark_closed [EXTRACTED 1.00]
- **Human approval and revision loop** — docs_diagrams_lifecycle_visual_check_2048x1320_dark_recommended, docs_diagrams_lifecycle_visual_check_2048x1320_dark_needs_approval, docs_diagrams_lifecycle_visual_check_2048x1320_dark_failed, docs_diagrams_lifecycle_visual_check_2048x1320_dark_analyzing [EXTRACTED 1.00]
- **Revision loop back to analysis** — docs_diagrams_lifecycle_visual_check_2048x1320_dark_decided, docs_diagrams_lifecycle_visual_check_2048x1320_dark_revise, docs_diagrams_lifecycle_visual_check_2048x1320_dark_analyzing [EXTRACTED 1.00]
- **Terminal failure and exit states** — docs_diagrams_lifecycle_visual_check_2048x1320_dark_rejected, docs_diagrams_lifecycle_visual_check_2048x1320_dark_expired [EXTRACTED 1.00]
- **Decision phases contain five ordered states** — docs_diagrams_lifecycle_visual_check_2048x1320_light_draft, docs_diagrams_lifecycle_visual_check_2048x1320_light_analyzing, docs_diagrams_lifecycle_visual_check_2048x1320_light_recommended, docs_diagrams_lifecycle_visual_check_2048x1320_light_decided, docs_diagrams_lifecycle_visual_check_2048x1320_light_closed [EXTRACTED 1.00]
- **Human gates and recovery loop states** — docs_diagrams_lifecycle_visual_check_2048x1320_light_needs_approval, docs_diagrams_lifecycle_visual_check_2048x1320_light_revise, docs_diagrams_lifecycle_visual_check_2048x1320_light_failed [EXTRACTED 1.00]
- **Terminal exit states** — docs_diagrams_lifecycle_visual_check_2048x1320_light_rejected, docs_diagrams_lifecycle_visual_check_2048x1320_light_expired [EXTRACTED 1.00]
- **Optimize Request Roundtrip** — docs_diagrams_sequence_visual_check_1440x900_dark_charterer, docs_diagrams_sequence_visual_check_1440x900_dark_react_app, docs_diagrams_sequence_visual_check_1440x900_dark_fastapi, docs_diagrams_sequence_visual_check_1440x900_dark_postgres, docs_diagrams_sequence_visual_check_1440x900_dark_forecast, docs_diagrams_sequence_visual_check_1440x900_dark_optimizer, docs_diagrams_sequence_visual_check_1440x900_dark_accept, docs_diagrams_sequence_visual_check_1440x900_dark_run_analysis, docs_diagrams_sequence_visual_check_1440x900_dark_post_api_optimize, docs_diagrams_sequence_visual_check_1440x900_dark_load_vessels_ports, docs_diagrams_sequence_visual_check_1440x900_dark_vessel_rows, docs_diagrams_sequence_visual_check_1440x900_dark_forecast_rates, docs_diagrams_sequence_visual_check_1440x900_dark_rate_curve, docs_diagrams_sequence_visual_check_1440x900_dark_optimize_combos, docs_diagrams_sequence_visual_check_1440x900_dark_persist_recommendation [EXTRACTED 1.00]
- **Optimize Request Roundtrip** — docs_diagrams_sequence_visual_check_2048x1320_dark_charterer, docs_diagrams_sequence_visual_check_2048x1320_dark_react_app, docs_diagrams_sequence_visual_check_2048x1320_dark_fastapi, docs_diagrams_sequence_visual_check_2048x1320_dark_postgres, docs_diagrams_sequence_visual_check_2048x1320_dark_forecast, docs_diagrams_sequence_visual_check_2048x1320_dark_optimizer [EXTRACTED 1.00]
- **Optimize Request Roundtrip** — docs_diagrams_sequence_visual_check_2048x1320_light_charterer, docs_diagrams_sequence_visual_check_2048x1320_light_react_app, docs_diagrams_sequence_visual_check_2048x1320_light_fastapi, docs_diagrams_sequence_visual_check_2048x1320_light_postgres, docs_diagrams_sequence_visual_check_2048x1320_light_forecast, docs_diagrams_sequence_visual_check_2048x1320_light_optimizer [EXTRACTED 1.00]
- **Chartering Optimization Pipeline** — docs_diagrams_workflow_visual_check_1440x900_dark_charterer, docs_diagrams_workflow_visual_check_1440x900_dark_frontend, docs_diagrams_workflow_visual_check_1440x900_dark_nginx, docs_diagrams_workflow_visual_check_1440x900_dark_api, docs_diagrams_workflow_visual_check_1440x900_dark_forecast, docs_diagrams_workflow_visual_check_1440x900_dark_optimizer, docs_diagrams_workflow_visual_check_1440x900_dark_scheduler, docs_diagrams_workflow_visual_check_1440x900_dark_db, docs_diagrams_workflow_visual_check_1440x900_dark_freight, docs_diagrams_workflow_visual_check_1440x900_dark_fleet [EXTRACTED 1.00]
- **Main optimization flow** — docs_diagrams_workflow_visual_check_2048x1320_dark_enter_cargo, docs_diagrams_workflow_visual_check_2048x1320_dark_run_analysis, docs_diagrams_workflow_visual_check_2048x1320_dark_post_api_optimize, docs_diagrams_workflow_visual_check_2048x1320_dark_forecast_rates, docs_diagrams_workflow_visual_check_2048x1320_dark_feasibility_filter, docs_diagrams_workflow_visual_check_2048x1320_dark_cost_plus_risk, docs_diagrams_workflow_visual_check_2048x1320_dark_spot_vs_contract [EXTRACTED 1.00]
- **Policy gates** — docs_diagrams_workflow_visual_check_2048x1320_dark_spot_vs_contract, docs_diagrams_workflow_visual_check_2048x1320_dark_no_solution, docs_diagrams_workflow_visual_check_2048x1320_dark_approve_gate [EXTRACTED 1.00]
- **Decision support loop** — docs_diagrams_workflow_visual_check_2048x1320_dark_what_if_sim, docs_diagrams_workflow_visual_check_2048x1320_dark_decision_card, docs_diagrams_workflow_visual_check_2048x1320_dark_timing_advisor [EXTRACTED 1.00]
- **Chartering Main Optimization Flow** — docs_diagrams_workflow_visual_check_2048x1320_light_enter_cargo, docs_diagrams_workflow_visual_check_2048x1320_light_run_analysis, docs_diagrams_workflow_visual_check_2048x1320_light_forecast_rates, docs_diagrams_workflow_visual_check_2048x1320_light_feasibility_filter, docs_diagrams_workflow_visual_check_2048x1320_light_cost_plus_risk, docs_diagrams_workflow_visual_check_2048x1320_light_spot_vs_contract [EXTRACTED 1.00]
- **Decision and Review Loop** — docs_diagrams_workflow_visual_check_2048x1320_light_decision_card, docs_diagrams_workflow_visual_check_2048x1320_light_approve_gate, docs_diagrams_workflow_visual_check_2048x1320_light_timing_advisor [EXTRACTED 1.00]

## Communities (60 total, 33 thin omitted)

### Community 0 - "Frontend Dependencies"
Cohesion: 0.06
Nodes (54): dependencies, framer-motion, react, react-dom, recharts, devDependencies, @types/react, @types/react-dom (+46 more)

### Community 1 - "Market Data Connectors"
Cohesion: 0.07
Nodes (27): _cache_path(), cache_read(), cache_write(), http_get(), parse_csv_rows(), fetch_bunker_trend(), _fetch_eia_residual_factor(), fetch_commodities() (+19 more)

### Community 2 - "Realtime Data Fetching"
Cohesion: 0.09
Nodes (42): create_features(), load_contracts(), load_ports(), fetch_all_realtime(), fetch_bunker_realtime(), fetch_commodity_realtime(), fetch_congestion_realtime(), _fetch_contracts() (+34 more)

### Community 3 - "Cost Feasibility Engines"
Cohesion: 0.06
Nodes (11): CostBreakdown, CostEngine, FeasibilityEngine, FeasibleVessel, CharteringOptimizer, _score(), OptimizationResult, TimingAdvisor (+3 more)

### Community 4 - "Synthetic Data Seeding"
Cohesion: 0.11
Nodes (25): generate_congestion_data(), generate_ports(), generate_synthetic_bunker_prices(), generate_synthetic_commodity_prices(), generate_synthetic_freight_rates(), generate_vessels(), refresh_vessels_from_marinesia(), seed_database() (+17 more)

### Community 5 - "Architecture Overview Diagram"
Cohesion: 0.07
Nodes (36): Charterer Browser, Maritime Chartering Decision Engine Diagram, FastAPI main.py, Fleet APIs VesselAPI AISStream, Forecast Engine Prophet XGBoost, Market Data EIA FRED Stooq yfinance, Nginx static proxy, Optimization Engine feasibility cost risk timing (+28 more)

### Community 6 - "Live Sync Service"
Cohesion: 0.14
Nodes (14): get_live_port_metrics(), get_live_vessel_updates(), _log_run(), sync_all(), sync_bunker(), sync_commodities(), sync_congestion_from_live_metrics(), sync_dataset() (+6 more)

### Community 7 - "External API Integration"
Cohesion: 0.08
Nodes (20): Vessel Positions and Port Congestion via AISStream, Bunker Fuel Prices via EIA trend, Freight Rates via yfinance BDRY proxy, realtime_fetcher live plus DB merger, sync_service to PostgreSQL flow, Backend Python dependency stack, POST api timing endpoint, CharteringOptimizer all vessel by port combos (+12 more)

### Community 8 - "Lifecycle Sequence Diagrams"
Cohesion: 0.11
Nodes (23): Recommendation Lifecycle Diagram, Optimize Request Roundtrip Sequence Diagram, Chartering Optimization Pipeline Workflow Diagram, Analyzing - engines running, Closed - charter fixed, Decided - spot vs contract, Draft - cargo entered, Expired - laycan passed (+15 more)

### Community 9 - "Architecture Annotations Panel"
Cohesion: 0.22
Nodes (19): Application notes (Forecaster feeds feasibility/cost/risk/optimizer chain; TimingAdvisor re-runs optimizer), Backend boundary (app_backend :8000/8420), Charterer (browser), Data notes (PostgreSQL 16 holds 14 tables incl vessels and recommendations; live market/fleet APIs enter via sync service), Docker Compose boundary, Edge annotations panel (REST endpoints on FastAPI:8000, Nginx serves frontend:3000), FastAPI (main.py :8000), Fleet APIs (VesselAPI AllStream) (+11 more)

### Community 10 - "Lifecycle State Machine"
Cohesion: 0.24
Nodes (16): Analyzing, Closed, Decided, Decision phases, Draft, Expired, Failed, Human waits + Recovery loop (+8 more)

### Community 11 - "Optimization Pipeline Stages"
Cohesion: 0.28
Nodes (16): Approve Gate, Chartering Optimization Pipeline, Cost plus Risk, Decision Card, Enter Cargo, Feasibility Filter, Forecast Rates, Gates (+8 more)

### Community 12 - "Dataflow Pipeline Stages"
Cohesion: 0.20
Nodes (15): Bunker + Commodity (live prices), 05 / Consume, Cost Risk Optimizer (spot vs contract), Dashboard (6 views), Fleet Feeds (VesselAPI AIS), Fleet Store (96 ships + congestion), Forecast Ensemble (Prophet plus XGBoost), Freight Rates (70k plus live BDRY) (+7 more)

### Community 13 - "Lifecycle Detailed States"
Cohesion: 0.24
Nodes (15): Analyzing (engines running), Closed (charter fixed), Decided (spot vs contract), Decision phases (section 01), Draft (cargo entered), Expired (laycan passed), Failed (recoverable error), Human waits + Recovery loop (section 02) (+7 more)

### Community 14 - "Optimize Request Sequence"
Cohesion: 0.19
Nodes (15): Accept, Charterer (browser), FastAPI (main.py :8000), Forecast (Prophet+XGBoost), forecast rates, load vessels + ports, optimize combos, Optimizer (spot vs contract) (+7 more)

### Community 16 - "AIS Worker Service"
Cohesion: 0.23
Nodes (6): _ais_consumer_loop(), get_port_for_coord(), is_in_bbox(), start_ais_worker(), stop_ais_worker(), _worker_thread_main()

### Community 17 - "Lifecycle Core States"
Cohesion: 0.36
Nodes (11): Analyzing (engines running), Closed (charter fixed), Decided (spot vs contract), Draft (cargo entered), Expired (laycan passed), Failed (recoverable error), Needs Approval (human gate), Recommendation Lifecycle (+3 more)

### Community 18 - "Decision Pipeline Features"
Cohesion: 0.22
Nodes (11): Approve Gate (approve modify reject), Cost plus Risk (voyage cost scoring), Decision Card (savings plus confidence), Enter Cargo (route plus laycan), Feasibility Filter (vessels x ports), Forecast Rates (Prophet plus XGBoost), No Solution (honest reason), Run Analysis (75k MT demo flow) (+3 more)

### Community 19 - "Architecture Components Light"
Cohesion: 0.24
Nodes (10): Charterer (Browser), FastAPI (main.py :8000), Fleet APIs (VesselAPI AISstream), Forecast Engine (Prophet plus XGBoost), Market Data (EIA FRED Stooq yfinance), Nginx (static proxy), Optimization Engine (Feasibility cost risk timing), PostgreSQL (maritime_chartering :5432) (+2 more)

### Community 20 - "Architecture Components Dark"
Cohesion: 0.24
Nodes (10): Charterer Browser, FastAPI main.py :8000, Fleet APIs VesselAPI AISStream, Forecast Engine Prophet plus XGBoost, Market Data EIA FRED Stooq yfinance, Nginx static plus proxy, Optimization Engine feasibility cost risk timing, PostgreSQL maritime_chartering :5432 (+2 more)

### Community 21 - "Dataflow Stores Feeds"
Cohesion: 0.27
Nodes (10): Bunker + Commodity (live prices), Cost Risk Optimizer (spot vs contract), Dashboard (6 views), Fleet Feeds (Vessel API AIS), Fleet Store (96 ships + congestion), Forecast Ensemble (Prophet plus XGBoost), Freight Rates (70k plus live BDRY), Market Feeds (EIA FRED) (+2 more)

### Community 22 - "Core System Components"
Cohesion: 0.22
Nodes (10): FastAPI, Charterer, PostgreSQL, Fleet APIs, Forecast Engine, Market Data, React Dashboard, Nginx (+2 more)

### Community 23 - "Frontend Cloud Build"
Cohesion: 0.33
Nodes (7): Cloud Run Backend URL (asia-south1), Docker Build Step (gcr.io/cloud-builders/docker), Dockerfile.frontend.gcp, Frontend Container Image (Artifact Registry), GCP Project (project-7deab4fd-2ae4-45a3-a64), Artifact Registry (maritime), VITE_API_URL Build Arg

### Community 24 - "Sequence Participants Set"
Cohesion: 0.33
Nodes (6): Charterer browser participant, FastAPI main.py participant, Forecast Prophet XGBoost participant, Optimizer spot vs contract participant, Postgres 14 tables participant, React App dashboard participant

### Community 25 - "Sequence Flow Light"
Cohesion: 0.40
Nodes (6): Charterer (browser), FastAPI (main.py:8000), Forecast (Prophet+XGBoost), Optimizer (spot vs contract), Postgres (14 tables), React App (dashboard)

### Community 26 - "Sequence Flow Dark"
Cohesion: 0.33
Nodes (6): Charterer (browser), FastAPI (main.py :8000), Forecast (Prophet+XGBoost), Optimizer (spot vs contract), Postgres (14 tables), React App (dashboard)

### Community 27 - "Docker Compose Services"
Cohesion: 0.50
Nodes (4): GCP Cloud Build backend image, Backend uvicorn service port 8000, Postgres 16 db service maritime_chartering, Frontend service port 3000

## Ambiguous Edges - Review These
- `GCP Cloud Build backend image` → `Backend uvicorn service port 8000`  [AMBIGUOUS]
  cloudbuild.backend.yaml · relation: references

## Knowledge Gaps
- **96 isolated node(s):** `@types/react`, `@types/react-dom`, `Maritime Chartering Decision Engine`, `Decision Dashboard (React)`, `POST /api/optimize full pipeline` (+91 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 200 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **33 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `CharteringOptimizer` connect `Cost Feasibility Engines` to `Realtime Data Fetching`?**
  _High betweenness centrality (0.017) - this node is a cross-community bridge._
- **Are the 6 inferred relationships involving `CharteringOptimizer` (e.g. with `optimize()` and `run_scenario()`) actually correct?**
  _`CharteringOptimizer` has 6 INFERRED edges - model-reasoned connections that need verification._
- **What connects `@types/react`, `@types/react-dom`, `Maritime Chartering Decision Engine` to the rest of the system?**
  _96 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Frontend Dependencies` be split into smaller, more focused modules?**
  _Cohesion score 0.0563165905631659 - nodes in this community are weakly interconnected._
- **Why does `RiskEngine` connect `Cost Feasibility Engines` to `Realtime Data Fetching`?**
  _High betweenness centrality (0.010) - this node is a cross-community bridge._
- **Are the 7 inferred relationships involving `optimize()` (e.g. with `Port` and `Recommendation`) actually correct?**
  _`optimize()` has 7 INFERRED edges - model-reasoned connections that need verification._

### Low-confidence Hints
_AMBIGUOUS edges — the extractor was unsure. Verify before acting on these._

- **What is the exact relationship between `GCP Cloud Build backend image` and `Backend uvicorn service port 8000`?**
  _Edge tagged AMBIGUOUS (relation: references) - confidence is low._