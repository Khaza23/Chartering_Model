import React, { useState, useEffect } from 'react';
import DataStatus from './components/DataStatus';
import ExecutiveDecision from './components/ExecutiveDecision';
import ForecastView from './components/ForecastView';
import VesselComparison from './components/VesselComparison';
import ContractComparison from './components/ContractComparison';
import ScenarioSimulator from './components/ScenarioSimulator';
import Timing from './components/Timing';
import WhyPanel from './components/WhyPanel';
import './App.css';

const API_BASE = import.meta.env.VITE_API_URL || '/api';

function App() {
  const [activeScreen, setActiveScreen] = useState('decision');
  const [loading, setLoading] = useState(false);
  const [recommendation, setRecommendation] = useState(null);
  const [forecast, setForecast] = useState(null);
  const [feasibility, setFeasibility] = useState(null);
  const [costData, setCostData] = useState(null);
  const [timing, setTiming] = useState(null);
  const [lastParams, setLastParams] = useState(null);
  const [error, setError] = useState(null);
  const [dataStatus, setDataStatus] = useState(null);

  useEffect(() => {
    fetch(`${API_BASE}/data-status`)
      .then(r => r.json())
      .then(setDataStatus)
      .catch(() => {});
  }, []);

  const runAnalysis = async (params) => {
    setLoading(true);
    setError(null);
    try {
      const [optRes, foreRes, feasRes, costRes] = await Promise.all([
        fetch(`${API_BASE}/optimize`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(params)
        }).then(r => r.json()),
        fetch(`${API_BASE}/forecast`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            route: `${params.origin}-${params.destination}`,
            vessel_class: 'panamax',
            forecast_days: 30
          })
        }).then(r => r.json()),
        fetch(`${API_BASE}/feasibility`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(params)
        }).then(r => r.json()),
        fetch(`${API_BASE}/cost`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            freight_rate: params.current_freight_rate,
            cargo_quantity: params.cargo_quantity,
            vessel_id: 1,
            port_name: params.destination,
            origin: params.origin
          })
        }).then(r => r.json())
      ]);

      setRecommendation(optRes);
      setForecast(foreRes);
      setFeasibility(feasRes);
      setCostData(costRes);
      setLastParams(params);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const runTiming = async (params) => {
    if (!params) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/timing`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ base_params: params })
      }).then(r => r.json());
      setTiming(res);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const screens = [
    { id: 'decision', label: 'Decision' },
    { id: 'forecast', label: 'Forecast' },
    { id: 'vessels', label: 'Vessels' },
    { id: 'contracts', label: 'Contracts' },
    { id: 'scenario', label: 'What-If' },
    { id: 'timing', label: 'Timing' },
    { id: 'why', label: 'Why?' }
  ];

  return (
    <div className="app">
      <nav className="top-nav">
        <div className="nav-left">
          <span className="brand">SAIL</span>
          <span className="brand-sub">Chartering Engine</span>
        </div>
        <div className="nav-tabs">
          {screens.map(s => (
            <button
              key={s.id}
              className={`nav-tab ${activeScreen === s.id ? 'active' : ''}`}
              onClick={() => setActiveScreen(s.id)}
            >
              {s.label}
            </button>
          ))}
        </div>
        <div className="nav-right">
          <DataStatus status={dataStatus} compact />
        </div>
      </nav>

      <main className="main-content" key={activeScreen}>
        {error && <div className="error-banner">{error}</div>}
        {dataStatus && Object.values(dataStatus.datasets || {}).some(d => d && d.stale) && (
          <div className="stale-banner" role="status">
            <strong>Using seeded baseline for some datasets.</strong>{' '}
            Add free keys (FRED, EIA, Stooq, AISStream) and POST /api/sync to go live.
          </div>
        )}
        {dataStatus && <DataStatus status={dataStatus} />}

        {activeScreen === 'decision' && (
          <ExecutiveDecision
            onRunAnalysis={runAnalysis}
            recommendation={recommendation}
            loading={loading}
          />
        )}
        {activeScreen === 'forecast' && (
          <ForecastView forecast={forecast} loading={loading} />
        )}
        {activeScreen === 'vessels' && (
          <VesselComparison feasibility={feasibility} recommendation={recommendation} loading={loading} />
        )}
        {activeScreen === 'contracts' && (
          <ContractComparison costData={costData} loading={loading} />
        )}
        {activeScreen === 'scenario' && (
          <ScenarioSimulator onRunScenario={runAnalysis} />
        )}
        {activeScreen === 'timing' && (
          <Timing
            timing={timing}
            loading={loading}
            hasParams={!!lastParams}
            onAssessTiming={() => runTiming(lastParams)}
          />
        )}
        {activeScreen === 'why' && (
          <WhyPanel recommendation={recommendation} />
        )}
      </main>
    </div>
  );
}

export default App;
