import React, { useState } from 'react';

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

const ExecutiveDecision = ({ onRunAnalysis, recommendation, loading }) => {
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

  const handleChange = (field, value) => {
    setParams(prev => ({ ...prev, [field]: value }));
  };

  const totalQty = Number(params.cargo_quantity) || 0;
  const shipCount = Math.max(1, Math.min(20, Number(params.num_ships) || 1));
  const perShip = totalQty > 0 ? Math.round(totalQty / shipCount) : 0;
  const suggested = suggestShips(totalQty);
  const showSuggest = totalQty > 0 && suggested !== shipCount;

  const handleSubmit = () => {
    onRunAnalysis({
      cargo_quantity: Number(params.cargo_quantity),
      num_ships: Math.max(1, Math.min(20, Number(params.num_ships) || 1)),
      origin: params.origin,
      destination: params.destination,
      laycan_start: params.laycan_start,
      laycan_end: params.laycan_end,
      required_voyages: Number(params.required_voyages),
    });
  };

  const formatCost = (val) => {
    if (!val) return '--';
    if (val >= 1000000) return `$${(val / 1000000).toFixed(1)}M`;
    if (val >= 1000) return `$${(val / 1000).toFixed(0)}K`;
    return `$${val.toFixed(0)}`;
  };

  const getActionLabel = (action) => {
    const labels = {
      'BOOK_NOW': 'BOOK SPOT TONNAGE',
      'SHORT_CONTRACT': 'ENTER SHORT-TERM CONTRACT',
      'MEDIUM_CONTRACT': 'ENTER 6-VOYAGE CONTRACT',
      'WAIT': 'WAIT FOR BETTER RATES',
      'SWITCH_ROUTE': 'CONSIDER ALTERNATE ROUTE'
    };
    return labels[action] || action;
  };

  const getRiskBadge = (level) => {
    const cls = level === 'LOW' ? 'badge-low' : level === 'MEDIUM' ? 'badge-medium' : 'badge-high';
    return <span className={`badge ${cls}`}>{level}</span>;
  };

  return (
    <div>
      <div className="input-panel">
        <div className="card-header">
          <div>
            <div className="card-title">Chartering Parameters</div>
            <div className="card-subtitle">Freight rate auto-fetched live</div>
          </div>
          <button className="btn-primary" onClick={handleSubmit} disabled={loading}>
            {loading ? 'Analyzing...' : 'Run Analysis'}
          </button>
        </div>
        <div className="input-grid">
          <div className="input-group cargo-fleet-span">
            <label>Total Cargo (MT) · Ships</label>
            <div className="cargo-fleet-row">
              <input type="number" min="1000" step="1000" value={params.cargo_quantity}
                onChange={e => handleChange('cargo_quantity', e.target.value)}
                title="Total cargo to move — split across ships"
                style={{ flex: 1 }} />
              <div className="ships-stepper">
                <button type="button" className="stepper-btn" aria-label="Fewer ships"
                  onClick={() => handleChange('num_ships', Math.max(1, (Number(params.num_ships) || 1) - 1))}>−</button>
                <input type="number" min="1" max="20" step="1" value={params.num_ships}
                  onChange={e => handleChange('num_ships', e.target.value)}
                  title="Number of ships (1–20)" aria-label="Number of ships" />
                <button type="button" className="stepper-btn" aria-label="More ships"
                  onClick={() => handleChange('num_ships', Math.min(20, (Number(params.num_ships) || 1) + 1))}>+</button>
              </div>
            </div>
            <div className="fleet-hint">
              <span>≈ {perShip.toLocaleString()} MT / ship</span>
              {showSuggest && (
                <>
                  <span className="fleet-dot">·</span>
                  <span>Suggested: {suggested} ship{suggested > 1 ? 's' : ''}</span>
                  <button type="button" className="fleet-apply"
                    onClick={() => handleChange('num_ships', suggested)}>Apply</button>
                </>
              )}
            </div>
          </div>
          <div className="input-group">
            <label>Origin</label>
            <select value={params.origin} onChange={e => handleChange('origin', e.target.value)}>
              <option>Australia</option>
              <option>South Africa</option>
              <option>Indonesia</option>
            </select>
          </div>
          <div className="input-group">
            <label>Destination</label>
            <select value={params.destination} onChange={e => handleChange('destination', e.target.value)}>
              <option>Paradip</option>
              <option>Dhamra</option>
              <option>Gangavaram</option>
              <option>Vizag</option>
              <option>Mundra</option>
            </select>
          </div>
          <div className="input-group">
            <label>Laycan Start</label>
            <input type="date" value={params.laycan_start}
              onChange={e => handleChange('laycan_start', e.target.value)} />
          </div>
          <div className="input-group">
            <label>Laycan End</label>
            <input type="date" value={params.laycan_end}
              onChange={e => handleChange('laycan_end', e.target.value)} />
          </div>
          <div className="input-group">
            <label>Required Voyages</label>
            <select value={params.required_voyages} onChange={e => handleChange('required_voyages', e.target.value)}>
              <option value={1}>1 (Spot)</option>
              <option value={3}>3 Voyages</option>
              <option value={6}>6 Voyages</option>
              <option value={12}>12 Voyages</option>
            </select>
          </div>
        </div>
      </div>

      {loading && (
        <div className="loading-spinner">
          <div className="spinner" />
        </div>
      )}

      {!loading && !recommendation && (
        <div className="empty-state">
          <div className="empty-state-icon">⚓</div>
          <div className="empty-state-text">No analysis run yet</div>
          <div className="empty-state-sub">Configure parameters above and click "Run Analysis"</div>
        </div>
      )}

      {!loading && recommendation && (
        <>
          <div className="recommendation-banner">
            <div style={{ fontSize: '10px', color: 'var(--ink-tertiary)', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: '6px', fontWeight: '600' }}>
              Recommendation
            </div>
            <div className="rec-action">{getActionLabel(recommendation.action)}</div>
            {recommendation.resolved_freight_rate && (
              <div style={{ fontSize: '12px', color: 'var(--ink-muted)', marginTop: '4px' }}>
                Live rate used: ${Number(recommendation.resolved_freight_rate).toFixed(2)}/MT
                {recommendation.fleet && (
                  <span style={{ marginLeft: '8px', color: 'var(--ink-tertiary)' }}>
                    · Fleet: {recommendation.fleet.num_ships} × {(recommendation.fleet.per_ship_quantity ?? 0).toLocaleString()} MT
                    ({(recommendation.fleet.total_quantity ?? 0).toLocaleString()} MT total)
                  </span>
                )}
              </div>
            )}
            <div className="rec-meta">
              <div className="rec-meta-item">
                <span className="rec-meta-label">Expected Saving</span>
                <span className="rec-meta-value positive">
                  {formatCost(recommendation.expected_savings)}
                </span>
              </div>
              <div className="rec-meta-item">
                <span className="rec-meta-label">Risk</span>
                <span className="rec-meta-value">
                  {getRiskBadge(recommendation.risk_level)}
                </span>
              </div>
              <div className="rec-meta-item">
                <span className="rec-meta-label">Confidence</span>
                <span className="rec-meta-value">
                  {(recommendation.confidence * 100).toFixed(0)}%
                </span>
              </div>
              <div className="rec-meta-item">
                <span className="rec-meta-label">Total Cost</span>
                <span className="rec-meta-value">
                  {formatCost(recommendation.expected_total_cost)}
                </span>
              </div>
              <div className="rec-meta-item">
                <span className="rec-meta-label">Cost / MT</span>
                <span className="rec-meta-value">
                  ${recommendation.cost_per_mt?.toFixed(1)}
                </span>
              </div>
            </div>
          </div>

          <div className="metric-row">
            <div className="metric-card">
              <div className="metric-label">Vessel</div>
              <div className="metric-value" style={{ fontSize: '16px' }}>
                {recommendation.vessel?.name || '--'}
              </div>
              <div style={{ fontSize: '11px', color: 'var(--ink-subtle)', marginTop: '2px' }}>
                {recommendation.vessel?.class} · {recommendation.vessel?.capacity?.toLocaleString()} MT cap.
                {recommendation.fleet?.per_ship_quantity != null && (
                  <> · parcel {(recommendation.fleet.per_ship_quantity ?? 0).toLocaleString()} MT/ship</>
                )}
              </div>
            </div>
            <div className="metric-card">
              <div className="metric-label">Port</div>
              <div className="metric-value" style={{ fontSize: '16px' }}>
                {recommendation.port || '--'}
              </div>
            </div>
            <div className="metric-card">
              <div className="metric-label">Contract</div>
              <div className="metric-value" style={{ fontSize: '16px' }}>
                {recommendation.contract_type?.replace('_', ' ').toUpperCase()}
              </div>
              <div style={{ fontSize: '11px', color: 'var(--ink-subtle)', marginTop: '2px' }}>
                {recommendation.voyage_count} voyages
              </div>
            </div>
          </div>

          <div className="two-col">
            <div className="card">
              <div className="card-header">
                <div className="card-title">Cost Comparison</div>
              </div>
              <div className="cost-breakdown">
                {recommendation.all_options?.map((opt, i) => (
                    <div key={i} className="cost-row" style={opt.type === recommendation.contract_type ? { background: 'var(--primary-light)', borderRadius: '6px', padding: '8px 10px', boxShadow: 'inset 0 0 0 1px var(--hairline)' } : {}}>
                      <div>
                        <span className="cost-label">{opt.type?.replace('_', ' ').toUpperCase()}</span>
                        <span style={{ fontSize: '11px', color: 'var(--ink-tertiary)', marginLeft: '8px' }}>
                        ({opt.voyages} voyage{opt.voyages > 1 ? 's' : ''})
                      </span>
                    </div>
                    <div className="cost-value">{formatCost(opt.total_cost)}</div>
                  </div>
                ))}
              </div>
            </div>

            <div className="card">
              <div className="card-header">
                <div className="card-title">Reasoning</div>
              </div>
              <div className="reasoning-list">
                {recommendation.reasoning?.map((reason, i) => (
                  <div key={i} className="reasoning-item">
                    <div className="reasoning-text">{reason}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {recommendation.vessel_options?.length > 1 && (
            <div className="card" style={{ marginTop: '20px' }}>
              <div className="card-header">
                <div className="card-title">Top Vessel × Port Alternatives</div>
                <div className="card-subtitle">Ranked by total cost — winner varies with rates, bunker, and congestion</div>
              </div>
              <div className="cost-breakdown">
                {recommendation.vessel_options.slice(0, 5).map((o) => (
                  <div key={`${o.vessel_id}-${o.port_name}-${o.type}`} className="cost-row">
                    <div>
                      <span className="cost-label">{o.vessel_name} → {o.port_name}</span>
                      <span style={{ fontSize: '11px', color: 'var(--ink-tertiary)', marginLeft: '8px' }}>
                        {o.vessel_class} · {o.type?.replace('_', ' ')} · score {(o.feasibility_score * 100).toFixed(0)}
                      </span>
                    </div>
                    <div className="cost-value">{formatCost(o.total_cost)}</div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
};

export default ExecutiveDecision;
