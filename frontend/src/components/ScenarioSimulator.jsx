import React, { useState } from 'react';
import { ScenarioSkeleton } from './Skeleton';

const API_BASE = import.meta.env.VITE_API_URL || '/api';

const getDefaultDates = () => {
  const start = new Date();
  start.setDate(start.getDate() + 3);
  const end = new Date();
  end.setDate(end.getDate() + 14);
  return {
    start: start.toISOString().split('T')[0],
    end: end.toISOString().split('T')[0]
  };
};

const REF_PARCEL_MT = 75000;

const suggestShips = (total) => {
  const t = Number(total) || 0;
  if (t <= 0) return 1;
  return Math.max(1, Math.min(20, Math.ceil(t / REF_PARCEL_MT)));
};

const ScenarioSimulator = ({ onRunScenario }) => {
  const defaultDates = getDefaultDates();
  const [params, setParams] = useState({
    cargo_quantity: 75000,
    num_ships: 1,
    origin: 'Australia',
    destination: 'Paradip',
    laycan_start: defaultDates.start,
    laycan_end: defaultDates.end,
    required_voyages: 6
  });

  const totalQty = Number(params.cargo_quantity) || 0;
  const shipCount = Math.max(1, Math.min(20, Number(params.num_ships) || 1));
  const perShip = totalQty > 0 ? Math.round(totalQty / shipCount) : 0;
  const suggested = suggestShips(totalQty);
  const showSuggest = totalQty > 0 && suggested !== shipCount;

  const [scenarios, setScenarios] = useState([
    { name: 'Freight +10%', freight_change_pct: 10, bunker_change_pct: 0, congestion_change: 0, delay_change_hours: 0 },
    { name: 'Bunker +20%', freight_change_pct: 0, bunker_change_pct: 20, congestion_change: 0, delay_change_hours: 0 },
    { name: 'Port Congestion +30', freight_change_pct: 0, bunker_change_pct: 0, congestion_change: 30, delay_change_hours: 0 },
    { name: 'Combined Stress', freight_change_pct: 15, bunker_change_pct: 15, congestion_change: 20, delay_change_hours: 6 }
  ]);

  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);

  const runScenario = async (scenario) => {
    setLoading(true);
    try {
      const baseParams = {
        cargo_quantity: Number(params.cargo_quantity),
        num_ships: Math.max(1, Math.min(20, Number(params.num_ships) || 1)),
        origin: params.origin,
        destination: params.destination,
        laycan_start: params.laycan_start,
        laycan_end: params.laycan_end,
        required_voyages: Number(params.required_voyages),
      };
      const response = await fetch(`${API_BASE}/scenario`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          base_params: baseParams,
          freight_change_pct: scenario.freight_change_pct,
          bunker_change_pct: scenario.bunker_change_pct,
          congestion_change: scenario.congestion_change,
          delay_change_hours: scenario.delay_change_hours
        })
      });
      const data = await response.json();
      setResults({ ...data, scenario_name: scenario.name });
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const formatCost = (val) => {
    if (!val) return '--';
    if (val >= 1000000) return `$${(val / 1000000).toFixed(1)}M`;
    if (val >= 1000) return `$${(val / 1000).toFixed(0)}K`;
    return `$${val.toFixed(0)}`;
  };

  return (
    <div>
      <div className="input-panel">
        <div className="card-header">
          <div>
            <div className="card-title">What-If Simulator</div>
            <div className="card-subtitle">Adjust market conditions and see how recommendations change</div>
          </div>
        </div>
        <div className="input-grid">
          <div className="input-group cargo-fleet-span">
            <label>Total Cargo (MT) · Ships</label>
            <div className="cargo-fleet-row">
              <input type="number" min="1000" step="1000" value={params.cargo_quantity}
                onChange={e => setParams(p => ({ ...p, cargo_quantity: e.target.value }))}
                title="Total cargo to move — split across ships"
                style={{ flex: 1 }} />
              <div className="ships-stepper">
                <button type="button" className="stepper-btn" aria-label="Fewer ships"
                  onClick={() => setParams(p => ({ ...p, num_ships: Math.max(1, (Number(p.num_ships) || 1) - 1) }))}>−</button>
                <input type="number" min="1" max="20" step="1" value={params.num_ships}
                  onChange={e => setParams(p => ({ ...p, num_ships: e.target.value }))}
                  title="Number of ships (1–20)" aria-label="Number of ships" />
                <button type="button" className="stepper-btn" aria-label="More ships"
                  onClick={() => setParams(p => ({ ...p, num_ships: Math.min(20, (Number(p.num_ships) || 1) + 1) }))}>+</button>
              </div>
            </div>
            <div className="fleet-hint">
              <span>≈ {perShip.toLocaleString()} MT / ship</span>
              {showSuggest && (
                <>
                  <span className="fleet-dot">·</span>
                  <span>Suggested: {suggested} ship{suggested > 1 ? 's' : ''}</span>
                  <button type="button" className="fleet-apply"
                    onClick={() => setParams(p => ({ ...p, num_ships: suggested }))}>Apply</button>
                </>
              )}
            </div>
          </div>
          <div className="input-group">
            <label>Origin</label>
            <select value={params.origin} onChange={e => setParams(p => ({ ...p, origin: e.target.value }))}>
              <option>Australia</option>
              <option>South Africa</option>
              <option>Indonesia</option>
            </select>
          </div>
          <div className="input-group">
            <label>Destination</label>
            <select value={params.destination} onChange={e => setParams(p => ({ ...p, destination: e.target.value }))}>
              <option>Paradip</option>
              <option>Dhamra</option>
              <option>Gangavaram</option>
              <option>Vizag</option>
              <option>Mundra</option>
            </select>
          </div>
        </div>
      </div>

      <div className="card" style={{ marginBottom: '20px' }}>
        <div className="card-header">
          <div className="card-title">Preset Scenarios</div>
          <div className="card-subtitle">Click to simulate market stress conditions</div>
        </div>
        <div className="three-col">
          {scenarios.map((s, i) => (
            <button
              key={i}
              className="scenario-btn"
              onClick={() => runScenario(s)}
              disabled={loading}
            >
              <div className="scenario-btn-name">{s.name}</div>
              <div className="scenario-btn-detail">
                {s.freight_change_pct !== 0 && `Freight ${s.freight_change_pct > 0 ? '+' : ''}${s.freight_change_pct}%`}
                {s.bunker_change_pct !== 0 && ` · Bunker ${s.bunker_change_pct > 0 ? '+' : ''}${s.bunker_change_pct}%`}
                {s.congestion_change !== 0 && ` · Congestion +${s.congestion_change}`}
                {s.delay_change_hours !== 0 && ` · Delay +${s.delay_change_hours}h`}
              </div>
            </button>
          ))}
        </div>
      </div>

      {loading && <ScenarioSkeleton />}

      {!loading && results && (
        <div className="two-col">
          <div className="card">
            <div className="card-header">
              <div className="card-title">Base Case</div>
              <span className="badge badge-active">CURRENT</span>
            </div>
            <div className="cost-breakdown">
              <div className="cost-row">
                <span className="cost-label">Action</span>
                <span className="cost-value">{results.base_case?.action?.replace(/_/g, ' ')}</span>
              </div>
              <div className="cost-row">
                <span className="cost-label">Total Cost</span>
                <span className="cost-value">{formatCost(results.base_case?.total_cost)}</span>
              </div>
              <div className="cost-row">
                <span className="cost-label">Risk</span>
                <span className="cost-value">{results.base_case?.risk_level}</span>
              </div>
              <div className="cost-row">
                <span className="cost-label">Contract</span>
                <span className="cost-value">{results.base_case?.contract_type?.replace('_', ' ')}</span>
              </div>
              <div className="cost-row">
                <span className="cost-label">Savings</span>
                <span className="cost-value" style={{ color: 'var(--success)' }}>
                  {formatCost(results.base_case?.savings)}
                </span>
              </div>
            </div>
          </div>

          <div className="card card-accent" style={{ background: 'var(--primary-light)' }}>
            <div className="card-header">
              <div className="card-title">{results.scenario_name}</div>
              <span className="badge badge-medium">SCENARIO</span>
            </div>
            <div className="cost-breakdown">
              <div className="cost-row">
                <span className="cost-label">Action</span>
                <span className="cost-value">{results.scenario?.action?.replace(/_/g, ' ')}</span>
              </div>
              <div className="cost-row">
                <span className="cost-label">Total Cost</span>
                <span className="cost-value" style={{
                  color: results.impact?.cost_change > 0 ? 'var(--danger)' : 'var(--success)'
                }}>
                  {formatCost(results.scenario?.total_cost)}
                </span>
              </div>
              <div className="cost-row">
                <span className="cost-label">Risk</span>
                <span className="cost-value">{results.scenario?.risk_level}</span>
              </div>
              <div className="cost-row">
                <span className="cost-label">Contract</span>
                <span className="cost-value">{results.scenario?.contract_type?.replace('_', ' ')}</span>
              </div>
              <div className="cost-row">
                <span className="cost-label">Cost Change</span>
                <span className="cost-value" style={{
                  color: results.impact?.cost_change > 0 ? 'var(--danger)' : 'var(--success)'
                }}>
                  {results.impact?.cost_change > 0 ? '+' : ''}
                  {formatCost(results.impact?.cost_change)} ({results.impact?.cost_change_pct}%)
                </span>
              </div>
              {results.impact?.recommendation_changed && (
                <div className="cost-row">
                  <span className="cost-label">Recommendation Changed</span>
                  <span className="cost-value" style={{ color: 'var(--warning)' }}>YES</span>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ScenarioSimulator;
