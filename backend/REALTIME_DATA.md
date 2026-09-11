# Real-Time Data Integration

This document outlines the real-time data fetching architecture and the specific live data sources integrated into the application.

## 1. Real-Time Data Sources

The application connects to four external, free-tier data sources to enhance decision-making accuracy:

| Source | API / Provider | Connector File | API Key Env Var |
| :--- | :--- | :--- | :--- |
| **Freight Rates** | `yfinance` (BDRY ETF via Yahoo Finance) | `backend/data/connectors/freight_stooq.py` | None |
| **Commodity Prices** | Federal Reserve Economic Data (FRED) | `backend/data/connectors/commodities_fred.py` | `FRED_KEY` |
| **Bunker Fuel Prices** | U.S. Energy Information Administration (EIA) | `backend/data/connectors/bunker_eia.py` | `EIA_KEY` |
| **Vessel Positions / Congestion** | AISStream.io (WebSocket) | `backend/data/connectors/ais_worker.py` | `AISSTREAM_KEY` |

## 2. Detailed Data Breakdown

### A. Freight Rates (`freight_stooq.py`)
*   **Data:** Daily closing prices of the **BDRY ETF** (Global X Dry Bulk Shipping ETF), used as a proxy for the Baltic Dry Index (BDI).
*   **Derived Output:** The BDRY close is scaled to a BDI-equivalent value (`BDRY * 100`). This is transformed into per-route, per-vessel-class **$/metric-ton** rates for 8 routes (e.g., Australia-Paradip) across 4 vessel classes (Panamax, Supramax, Handymax, Capesize).
*   **Source Label:** `live/yfinance-bdi`

### B. Commodity Prices (`commodities_fred.py`)
*   **Data:** Three FRED monthly series:
    *   `PCOALAUUSDM`: Australia thermal coal price ($/MT).
    *   `PIORECRUSDM`: Iron ore price ($/MT).
    *   `WPU101707`: Steel mill products PPI index (scaled to $/MT).
*   **Derived Output:** A composite index value: `(coal_price + steel_price/7 + iron_ore_price) / 3`.
*   **Source Label:** `live/fred`

### C. Bunker Fuel Prices (`bunker_eia.py`)
*   **Data:** EIA weekly residual fuel oil spot price series.
*   **Derived Output:** The EIA trend factor (4-week momentum) is applied to baseline VLSFO ($590) and MGO ($760) prices, adding port-specific premiums for Paradip, Dhamra, Gangavaram, Vizag, and Mundra.
*   **Source Label:** `live/eia-trend`

### D. Vessel Positions and Port Congestion (`ais_worker.py`)
*   **Data:** Real-time AIS (Automatic Identification System) messages via AISStream.io WebSocket, covering 5 Indian bulk cargo ports:
    *   **East Coast:** Paradip, Dhamra, Gangavaram, Vizag.
    *   **West Coast:** Mundra.
*   **Derived Output:**
    *   **Congestion:** `congestion_index` (0-100), `expected_delay_hours`, and `vessels_waiting` count per port.
    *   **Vessels:** Live lat/lon, speed over ground (SOG), destination, ETA, and availability proxy ("open" vs. "laden").
*   **Source Label:** `live/aisstream`

## 3. Data Fetching Mechanisms

### On-Demand Fetching (Request-Time)
Every API endpoint requiring market data calls dedicated functions (e.g., `fetch_freight_realtime()`). These functions:
1.  Attempt a live fetch from the external API via the connector.
2.  Merge the fresh data with historical records from the PostgreSQL database (newer data wins).
3.  Fall back to DB-only data if the API call fails.

### Background Scheduler (APScheduler)
Two recurring jobs maintain data freshness:
*   **`daily_all` (Every 24 hours):** Syncs freight, commodities, bunker, and congestion data to the database.
*   **`hourly_congestion` (Every 1 hour):** Fetches live AIS port metrics and vessel updates, upserting them into the database.

### AIS WebSocket Worker
The AISStream connection runs as a **persistent background daemon thread**:
*   Connects via `wss://stream.aisstream.io/v0/stream`.
*   Subscribes to port bounding boxes and tracked vessel MMSIs.
*   Processes messages in real-time, storing them in thread-safe in-memory dictionaries.
*   Auto-reconnects on disconnection with a 15-second backoff.

### Manual Sync Trigger
The `POST /api/sync` endpoint allows users to manually trigger data syncs for individual datasets or all at once.

## 4. Frontend Consumption and Display

The React frontend uses standard HTTP polling (no WebSocket/SSE) to display live data:
*   **Status Badges:** `DataStatus.jsx` displays "Live" (green) or "Stale" (grey) badges for each dataset.
*   **Analysis Integration:** When a user clicks "Run Analysis", the backend fetches live data to populate the optimization, forecast, feasibility, and cost breakdown results.
*   **ForecastView:** Displays a 30-day freight rate forecast with upper/lower confidence bounds.
*   **VesselComparison:** Shows a table of feasible vessels with live AIS-derived data.

## Architecture Diagram

```
External APIs                    WebSocket (persistent)           Database
-----------                    ----------------------           ----------
Yahoo Finance (BDRY) --HTTP--> freight_stooq.py
FRED (coal/ore/steel) --HTTP--> commodities_fred.py
EIA (fuel oil trend) --HTTP--> bunker_eia.py                                              
AISStream.io ----------WS----> ais_worker.py ------> in-memory state
                                                |
                                     [Hourly/Daily Scheduler]
                                                |
                                          sync_service.py
                                                |
                                           PostgreSQL
                                                |
                                     realtime_fetcher.py  (on-demand, merges live + DB)
                                                |
                                          FastAPI Endpoints
                                                |
                                          React Frontend
```
