import React from 'react';

const VesselComparison = ({ feasibility, recommendation, loading }) => {
  if (loading) {
    return <div className="loading-spinner"><div className="spinner" /></div>;
  }

  if (!feasibility) {
    return (
      <div className="empty-state">
        <div className="empty-state-icon">🚢</div>
        <div className="empty-state-text">No vessel data</div>
        <div className="empty-state-sub">Run an analysis from the Decision tab first</div>
      </div>
    );
  }

  const formatNum = (val) => val ? val.toLocaleString() : '--';
  const uniqueVesselCount = feasibility.summary?.unique_feasible_vessels
    ?? new Set((feasibility.feasible_vessels || []).map((v) => v.vessel_id)).size;

  return (
    <div>
      <div className="metric-row">
        <div className="metric-card">
          <div className="metric-label">Total Candidates</div>
          <div className="metric-value">{feasibility.summary?.total_candidates || 0}</div>
        </div>
        <div className="metric-card">
          <div className="metric-label">Feasible Combos</div>
          <div className="metric-value" style={{ color: 'var(--success)' }}>
            {feasibility.summary?.feasible_count || 0}
          </div>
          <div style={{ fontSize: '11px', color: 'var(--ink-subtle)', marginTop: '2px' }}>
            {uniqueVesselCount} unique vessels
          </div>
        </div>
        <div className="metric-card">
          <div className="metric-label">Rejected</div>
          <div className="metric-value" style={{ color: 'var(--danger)' }}>
            {feasibility.summary?.rejected_count || 0}
          </div>
        </div>
        <div className="metric-card">
          <div className="metric-label">Pass Rate</div>
          <div className="metric-value">
            {feasibility.summary?.filter_pass_rate || 0}%
          </div>
        </div>
      </div>

      <div className="card" style={{ marginBottom: '20px' }}>
        <div className="card-header">
          <div className="card-title">Feasible Vessels × Ports</div>
          <div className="card-subtitle">
            One row per feasible vessel-port combination — same vessel scores differently per port (draft/LOA limits).
            RECOMMENDED marks the Decision-tab winner (cost + risk).
            {feasibility.fleet && (
              <> Parcel: {(feasibility.fleet.per_ship_quantity ?? 0).toLocaleString()} MT/ship
                ({feasibility.fleet.num_ships} ship{(feasibility.fleet.num_ships ?? 1) > 1 ? 's' : ''} ·{' '}
                {(feasibility.fleet.total_quantity ?? 0).toLocaleString()} MT total).</>
            )}
          </div>
        </div>
        <table className="vessel-table">
          <thead>
            <tr>
              <th>Vessel</th>
              <th>Class</th>
              <th>Capacity (MT)</th>
              <th>Draft (m)</th>
              <th>LOA (m)</th>
              <th>Beam (m)</th>
              <th>Port</th>
              <th>Score</th>
              <th>Daily Rate</th>
            </tr>
          </thead>
          <tbody>
            {feasibility.feasible_vessels?.map((v, i) => {
              const isWinner = !!recommendation?.vessel
                && v.vessel_id === recommendation.vessel.id
                && v.port_name === recommendation.port;
              return (
              <tr key={`${v.vessel_id}-${v.port_id ?? v.port_name}-${i}`} className={isWinner ? 'recommended' : ''}>
                <td>
                  <div style={{ fontWeight: 500 }}>{v.name}</div>
                  {isWinner && <span className="badge badge-active" style={{ marginTop: '3px' }}>RECOMMENDED</span>}
                </td>
                <td style={{ textTransform: 'capitalize' }}>{v.vessel_class}</td>
                <td>{formatNum(v.capacity)}</td>
                <td>{v.draft}</td>
                <td>{v.loa}</td>
                <td>{v.beam}</td>
                <td>{v.port_name}</td>
                <td>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <div style={{
                      width: '40px', height: '4px', background: 'var(--surface-3)',
                      borderRadius: '2px', overflow: 'hidden'
                    }}>
                      <div style={{
                        width: `${v.feasibility_score * 100}%`, height: '100%',
                        background: v.feasibility_score > 0.7 ? 'var(--success)' : 'var(--warning)',
                        borderRadius: '2px',
                        transition: 'width 0.5s ease'
                      }} />
                    </div>
                    <span style={{ fontSize: '12px', fontFeatureSettings: 'tnum', fontWeight: 500 }}>
                      {(v.feasibility_score * 100).toFixed(0)}
                    </span>
                  </div>
                </td>
                <td style={{ fontFeatureSettings: 'tnum', fontWeight: 500 }}>
                  ${v.daily_hire_rate?.toLocaleString()}
                </td>
              </tr>
              );
            })}
          </tbody>
        </table>
        {feasibility.feasible_vessels?.length === 0 && (
          <div style={{ padding: '28px', textAlign: 'center', color: 'var(--ink-subtle)', fontSize: '13px' }}>
            No feasible vessels found for the given constraints
          </div>
        )}
      </div>

      {feasibility.port_scores?.length > 0 && (
        <div className="card">
          <div className="card-header">
            <div className="card-title">Port Feasibility Scores</div>
          </div>
          <div className="bar-chart">
            {feasibility.port_scores.map((p, i) => (
              <div key={p.port_id} className="bar-item">
                <span className="bar-label">{p.port_name}</span>
                <div className="bar-track">
                  <div className="bar-fill" style={{
                    width: `${p.overall_score * 100}%`,
                    background: 'var(--primary)',
                    opacity: i === 0 ? 1 : 0.45
                  }} />
                </div>
                <span className="bar-value">{(p.overall_score * 100).toFixed(0)}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default VesselComparison;
