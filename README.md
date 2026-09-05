# Maritime Chartering Decision Engine

AI-powered vessel chartering optimization system for dry bulk cargo procurement. Forecasts freight rates, evaluates vessel feasibility, computes total voyage costs, and recommends the optimal chartering strategy (spot vs multi-voyage contract).

## Architecture

```
USER INPUT (Cargo / Route / Laycan)
        ↓
1. DATA LAYER (PostgreSQL)
        ↓
2. FREIGHT FORECAST ENGINE (Prophet + XGBoost Ensemble)
        ↓
3. FEASIBILITY ENGINE (Rule-based vessel/port filtering)
        ↓
4. COST ENGINE (Total voyage cost calculation)
        ↓
5. RISK ENGINE (Multi-factor risk scoring)
        ↓
6. OPTIMIZATION ENGINE (Spot vs contract comparison)
        ↓
7. DECISION + DASHBOARD (React)
```

## Quick Start

### Docker (Recommended)

```bash
docker-compose up --build
```

- Backend API: http://localhost:8000
- Frontend: http://localhost:3000
- API docs: http://localhost:8000/docs

### Manual Setup

**Backend:**

```bash
cd backend
pip install -r requirements.txt
python -c "from data.ingestion import seed_database; seed_database()"
uvicorn main:app --reload --port 8000
```

**Frontend:**

```bash
cd frontend
npm install
npm start
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/forecast` | POST | Freight rate forecasting |
| `/api/feasibility` | POST | Vessel/port feasibility check |
| `/api/cost` | POST | Total voyage cost calculation |
| `/api/optimize` | POST | Full optimization pipeline |
| `/api/scenario` | POST | What-if scenario simulation |
| `/api/recommendation/{id}` | GET | Retrieve saved recommendation |
| `/api/recommendation/{id}/action` | POST | Approve/modify/reject |
| `/api/vessels` | GET | List vessels |
| `/api/ports` | GET | List ports |
| `/api/backtest` | POST | Model backtesting |

## Project Structure

```
├── backend/
│   ├── main.py                    # FastAPI application
│   ├── api/                       # API route handlers
│   ├── models/
│   │   └── forecast_model.py      # Prophet + XGBoost ensemble
│   ├── optimization/
│   │   ├── feasibility.py         # Vessel/port filtering
│   │   ├── cost_engine.py         # Total cost calculation
│   │   └── optimizer.py           # Spot vs contract optimizer
│   ├── risk/
│   │   └── risk_engine.py         # Multi-factor risk scoring
│   ├── data/
│   │   ├── ingestion.py           # Synthetic data generation
│   │   └── preprocessing.py       # Feature engineering
│   ├── database/
│   │   ├── postgres.py            # DB connection
│   │   └── models_db.py          # SQLAlchemy models (9 tables)
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── App.js                 # Main app with routing
│       ├── App.css                # Stripe/Linear-inspired dark theme
│       └── components/
│           ├── ExecutiveDecision.js  # Screen 1: Decision card
│           ├── ForecastView.js       # Screen 2: Forecast chart
│           ├── VesselComparison.js   # Screen 3: Vessel table
│           ├── ContractComparison.js # Screen 4: Contract comparison
│           ├── ScenarioSimulator.js  # Screen 5: What-if simulator
│           └── WhyPanel.js          # Screen 6: Explainable AI
├── docker-compose.yml
├── Dockerfile.backend
├── Dockerfile.frontend
└── nginx.conf
```

## Database Schema

9 tables: `freight_rates`, `commodity_prices`, `bunker_prices`, `ports`, `vessels`, `port_congestion`, `cargo_requirements`, `contracts`, `forecasts`, `recommendations`

## Technology Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React + Recharts |
| Backend | FastAPI |
| Database | PostgreSQL + SQLAlchemy |
| ML | Prophet + XGBoost (ensemble) |
| Optimization | Brute-force enumeration (MVP) |
| Deployment | Docker Compose |

## Demo Flow

1. Enter cargo parameters (75,000 MT, Australia → Paradip, Oct 10-20)
2. Click "Run Analysis"
3. System runs: Forecast → Feasibility → Cost → Risk → Optimization
4. Returns recommendation with expected savings, risk level, and confidence
5. Navigate tabs to see forecast chart, vessel comparison, contract comparison
6. Use What-If simulator to stress-test the recommendation
7. Review "Why?" tab for explainable AI reasoning
