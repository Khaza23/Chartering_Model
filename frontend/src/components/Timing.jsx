import React from 'react';

const Timing = ({ timing, loading, onAssessTiming, hasParams }) => {
  const formatCost = (val) => {
    if (val === null || val === undefined) return '--';
    const abs = Math.abs(val);
    const sign = val < 0 ? '-' : '';
    if (abs >= 1000000) return `${sign}$${(abs / 1000000).toFixed(1)}M`;
    if (abs >= 1000) return `${sign}$${(abs / 1000).toFixed(0)}K`;
    return `${sign}$${abs.toFixed(0)}`;
  };

  const verdict = timing?.verdict;

  const verdictTitle = !verdict ? '' : verdict.decision === 'WAIT'
    ? `WAIT ~${verdict.wait_days} DAYS`
    : verdict.decision === 'GO_NOW'
      ? 'GO WITH CURRENT — BOOK NOW'
      : 'NO GOOD WINDOW';

  return (
    <div>
      <div className="input-panel">
        <div className="card-header">
          <div>
            <div className="card-title">Timing Assessment</div>
            <div className="card-subtitle">
              Re-runs the full analysis per wait date — same cargo and laycan, market moves on
            </div>
          </div>
          <button className="btn-primary" onClick={onAssessTiming} disabled={loading || !hasParams}>
            {loading ? 'Assessing...' : 'Assess Timing'}
          </button>
        </div>
        {!hasParams && (
          <div style={{ fontSize: '12px', color: 'var(--ink-subtle)', marginTop: '8px' }}>
            Run an analysis from the Decision tab first — timing uses those parameters.
          </div>
        )}
      </div>

      {loading && (
        <div className="loading-spinner">
          <div className="spinner" />
        </div>
      )}

      {!loading && !timing && (
        <div className="empty-state">
          <div className="empty-state-icon">⏳</div>
          <div className="empty-state-text">No timing assessment yet</div>
          <div className="empty-state-sub">Click "Assess Timing" to compare booking now vs waiting</div>
        </div>
      )}

      {!loading && timing && verdict && (
        <>
          <div className="recommendation-banner">
            <div style={{ fontSize: '10px', color: 'var(--ink-tertiary)', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: '6px', fontWeight: '600' }}>
              Timing Verdict
            </div>
            <div className="rec-action">{verdictTitle}</div>
            <div className="rec-meta">
              <div className="rec-meta-item">
                <span className="rec-meta-label">Expected Saving vs Now</span>
                <span className="rec-meta-value positive">
                  {verdict.decision === 'WAIT' ? formatCost(verdict.expected_savings_vs_now) : '--'}
                </span>
              </div>
              <div className="rec-meta-item">
                <span className="rec-meta-label">Best Date</span>
                <span className="rec-meta-value">
                  {verdict.wait_date || '--'}
                </span>
              </div>
              <div className="rec-meta-item">
                <span className="rec-meta-label">Confidence</span>
                <span className="rec-meta-value">
                  {(verdict.confidence * 100).toFixed(0)}%
                </span>
              </div>
            </div>
          </div>

          <div className="card" style={{ marginBottom: '20px' }}>
            <div className="card-header">
              <div className="card-title">Cost by Booking Date</div>
              <div className="card-subtitle">Same program, re-optimized per date</div>
            </div>
            <table className="contract-table">
              <thead>
                <tr>
                  <th>Wait</th>
                  <th>Date</th>
                  <th>Vessel</th>
                  <th>Contract</th>
                  <th>Total Cost</th>
                  <th>vs Now</th>
                  <th>Risk</th>
                </tr>
              </thead>
              <tbody>
                {timing.options?.map((o) => (
                  <tr
                    key={o.wait_days}
                    className={verdict.wait_days === o.wait_days && o.feasible ? 'recommended' : ''}
                    style={!o.feasible ? { opacity: 0.55 } : {}}
                  >
                    <td>{o.wait_days === 0 ? 'Now' : `${o.wait_days}d`}</td>
                    <td style={{ fontFeatureSettings: 'tnum' }}>{o.date}</td>
                    <td>
                      {o.feasible ? (
                        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                          <span style={{ fontWeight: 500 }}>{o.vessel?.name || '--'}</span>
                          {verdict.wait_days === o.wait_days && (
                            <span className="badge badge-active">BEST</span>
                          )}
                        </div>
                      ) : (
                        <span style={{ color: 'var(--danger)' }}>Infeasible</span>
                      )}
                    </td>
                    <td style={{ textTransform: 'capitalize' }}>
                      {o.feasible ? o.contract_type?.replace('_', ' ') : (o.reason || '--')}
                    </td>
                    <td style={{ fontFeatureSettings: 'tnum', fontWeight: 500 }}>
                      {o.feasible ? formatCost(o.total_cost) : '--'}
                    </td>
                    <td style={{ fontFeatureSettings: 'tnum', color: o.savings_vs_now > 0 ? 'var(--success)' : 'var(--ink-subtle)' }}>
                      {o.feasible && o.wait_days > 0 ? formatCost(o.savings_vs_now) : '--'}
                    </td>
                    <td>{o.feasible ? o.risk_level : '--'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="two-col">
            <div className="card">
              <div className="card-header">
                <div className="card-title">Why</div>
              </div>
              <div className="reasoning-list">
                {verdict.reasoning?.map((r, i) => (
                  <div key={i} className="reasoning-item">
                    <div className="reasoning-text">{r}</div>
                  </div>
                ))}
              </div>
            </div>
            <div className="card">
              <div className="card-header">
                <div className="card-title">Assumptions</div>
              </div>
              <div className="reasoning-list">
                {timing.assumptions?.map((a, i) => (
                  <div key={i} className="reasoning-item">
                    <div className="reasoning-text">{a}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
};

export default Timing;
