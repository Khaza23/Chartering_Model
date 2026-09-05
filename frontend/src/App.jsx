import React, { useState } from 'react';
import ExecutiveDecision from './components/ExecutiveDecision';
import ForecastView from './components/ForecastView';
import VesselComparison from './components/VesselComparison';
import ContractComparison from './components/ContractComparison';
import ScenarioSimulator from './components/ScenarioSimulator';
import WhyPanel from './components/WhyPanel';
import './App.css';

const API_BASE = '/api';

function App() {
  const [activeScreen, setActiveScreen] = useState('decision');
  const [loading, setLoading] = useState(false);
  const [recommendation, setRecommendation] = useState(null);
  const [forecast, setForecast] = useState(null);
  const [feasibility, setFeasibility] = useState(null);
  const [costData, setCostData] = useState(null);
  const [error, setError] = useState(null);

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
          <span className="status-dot" />
          <span className="status-text">System Online</span>
        </div>
      </nav>

      <main className="main-content">
        {error && <div className="error-banner">{error}</div>}

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
          <VesselComparison feasibility={feasibility} loading={loading} />
        )}
        {activeScreen === 'contracts' && (
          <ContractComparison costData={costData} loading={loading} />
        )}
        {activeScreen === 'scenario' && (
          <ScenarioSimulator onRunScenario={runAnalysis} />
        )}
        {activeScreen === 'why' && (
          <WhyPanel recommendation={recommendation} />
        )}
      </main>
    </div>
  );
}

export default App;
