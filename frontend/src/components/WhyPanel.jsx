import React from 'react';

const WhyPanel = ({ recommendation }) => {
  if (!recommendation) {
    return (
      <div className="empty-state">
        <div className="empty-state-icon">🔍</div>
        <div className="empty-state-text">No recommendation to explain</div>
        <div className="empty-state-sub">Run an analysis from the Decision tab first</div>
      </div>
    );
  }

  const featureImportance = recommendation.feature_importance || {};
  const maxImportance = Math.max(...Object.values(featureImportance), 1);

  const importanceItems = [
    { key: 'freight_trend', label: 'Freight Trend', color: 'var(--primary)' },
    { key: 'contract_discount', label: 'Contract Discount', color: '#475569' },
    { key: 'port_congestion', label: 'Port Congestion', color: 'var(--warning)' },
    { key: 'vessel_availability', label: 'Vessel Availability', color: 'var(--success)' },
    { key: 'bunker_price', label: 'Bunker Price', color: 'var(--danger)' },
    { key: 'laycan_flexibility', label: 'Laycan Flexibility', color: '#64748b' }
  ];

  const getActionLabel = (action) => {
    const labels = {
      'BOOK_NOW': 'Book Spot Tonnage',
      'SHORT_CONTRACT': 'Enter Short-Term Contract',
      'MEDIUM_CONTRACT': 'Enter 6-Voyage Contract',
      'WAIT': 'Wait for Better Rates',
      'SWITCH_ROUTE': 'Consider Alternate Route'
    };
    return labels[action] || action;
  };

  const getRiskColor = (level) => {
    return level === 'LOW' ? 'var(--success)' : level === 'MEDIUM' ? 'var(--warning)' : 'var(--danger)';
  };

  return (
    <div>
      <div className="two-col">
        <div className="card">
          <div className="card-header">
            <div className="card-title">Why This Recommendation?</div>
          </div>

          <div style={{ marginBottom: '20px' }}>
            <div style={{ fontSize: '10px', color: 'var(--ink-subtle)', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: '6px', fontWeight: '600' }}>
              Recommended Action
            </div>
            <div style={{ fontSize: '20px', fontWeight: 600, letterSpacing: '-0.2px' }}>
              {getActionLabel(recommendation.action)}
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px', marginBottom: '20px' }}>
            <div>
              <div style={{ fontSize: '10px', color: 'var(--ink-subtle)', marginBottom: '3px', textTransform: 'uppercase', letterSpacing: '0.5px', fontWeight: '600' }}>Expected Savings</div>
              <div style={{ fontSize: '16px', fontWeight: 600, color: 'var(--success)' }}>
                ${recommendation.expected_savings?.toLocaleString()}
              </div>
            </div>
            <div>
              <div style={{ fontSize: '10px', color: 'var(--ink-subtle)', marginBottom: '3px', textTransform: 'uppercase', letterSpacing: '0.5px', fontWeight: '600' }}>Confidence</div>
              <div style={{ fontSize: '16px', fontWeight: 600 }}>
                {(recommendation.confidence * 100).toFixed(0)}%
              </div>
            </div>
            <div>
              <div style={{ fontSize: '10px', color: 'var(--ink-subtle)', marginBottom: '3px', textTransform: 'uppercase', letterSpacing: '0.5px', fontWeight: '600' }}>Risk Level</div>
              <div style={{ fontSize: '16px', fontWeight: 600, color: getRiskColor(recommendation.risk_level) }}>
                {recommendation.risk_level}
              </div>
            </div>
            <div>
              <div style={{ fontSize: '10px', color: 'var(--ink-subtle)', marginBottom: '3px', textTransform: 'uppercase', letterSpacing: '0.5px', fontWeight: '600' }}>Savings %</div>
              <div style={{ fontSize: '16px', fontWeight: 600 }}>
                {recommendation.savings_pct}%
              </div>
            </div>
          </div>

          <div style={{ fontSize: '13px', fontWeight: 600, marginBottom: '10px' }}>Key Reasons</div>
          <div className="reasoning-list">
            {recommendation.reasoning?.map((reason, i) => (
              <div key={i} className="reasoning-item">
                <div className="reasoning-text">{reason}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="card">
          <div className="card-header">
            <div className="card-title">Decision Drivers</div>
            <div className="card-subtitle">Feature importance for this recommendation</div>
          </div>

          <div className="bar-chart" style={{ marginTop: '6px' }}>
            {importanceItems.map(item => {
              const value = featureImportance[item.key] || 0;
              return (
                <div key={item.key} className="bar-item">
                  <span className="bar-label">{item.label}</span>
                  <div className="bar-track">
                    <div className="bar-fill" style={{
                      width: `${(value / maxImportance) * 100}%`,
                      background: item.color
                    }} />
                  </div>
                  <span className="bar-value">{value.toFixed(0)}%</span>
                </div>
              );
            })}
          </div>

          <div style={{ marginTop: '24px' }}>
            <div className="card-header">
              <div className="card-title">Risk Breakdown</div>
            </div>
            {recommendation.all_options?.filter(o => o.type === recommendation.contract_type).map((opt, i) => (
              <div key={i}>
                {opt.risk_breakdown && (
                  <div className="bar-chart">
                    {[
                      { key: 'freight', label: 'Freight Risk', color: 'var(--primary)' },
                      { key: 'port', label: 'Port Risk', color: 'var(--warning)' },
                      { key: 'vessel', label: 'Vessel Risk', color: 'var(--success)' },
                      { key: 'contract', label: 'Contract Risk', color: 'var(--danger)' }
                    ].map(item => (
                      <div key={item.key} className="bar-item">
                        <span className="bar-label">{item.label}</span>
                        <div className="bar-track">
                          <div className="bar-fill" style={{
                            width: `${opt.risk_breakdown[item.key]}%`,
                            background: item.color
                          }} />
                        </div>
                        <span className="bar-value">{opt.risk_breakdown[item.key]?.toFixed(0)}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>

          <div className="hitl-box">
            <div className="hitl-label">Human-in-the-Loop</div>
            <div className="hitl-text">
              This is an AI-assisted recommendation. The procurement officer should review all factors
              before making a final chartering decision. The system does not autonomously execute trades.
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default WhyPanel;
