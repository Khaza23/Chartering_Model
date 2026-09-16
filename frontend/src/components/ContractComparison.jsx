import React from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts';

const ContractComparison = ({ costData, loading }) => {
  if (loading) {
    return <div className="loading-spinner"><div className="spinner" /></div>;
  }

  if (!costData) {
    return (
      <div className="empty-state">
        <div className="empty-state-icon">📋</div>
        <div className="empty-state-text">No cost data</div>
        <div className="empty-state-sub">Run an analysis from the Decision tab first</div>
      </div>
    );
  }

  const formatCost = (val) => {
    if (!val) return '--';
    if (val >= 1000000) return `$${(val / 1000000).toFixed(1)}M`;
    if (val >= 1000) return `$${(val / 1000).toFixed(0)}K`;
    return `$${val.toFixed(0)}`;
  };

  const chartData = costData.comparison?.map(c => ({
    name: c.type === 'spot' ? 'Spot' : `${c.voyages}V`,
    cost: c.total_cost / 1000000,
    savings: (costData.spot_cost?.total_cost - c.total_cost) / 1000000,
    type: c.type,
    voyages: c.voyages
  })) || [];

  const lowestCost = Math.min(...(costData.comparison?.map(c => c.total_cost) || [0]));

  const breakdown = costData.spot_cost?.breakdown;

  return (
    <div>
      <div className="two-col">
        <div className="card">
          <div className="card-header">
            <div>
              <div className="card-title">Spot Cost Breakdown</div>
              {costData.fleet?.num_ships > 1 && (
                <div className="card-subtitle">
                  Fleet total: {costData.fleet.num_ships} × {(costData.fleet.per_ship_quantity ?? 0).toLocaleString()} MT
                  ({(costData.fleet.total_quantity ?? 0).toLocaleString()} MT)
                </div>
              )}
            </div>
          </div>
          <div className="cost-breakdown">
            {breakdown && Object.entries(breakdown).map(([key, val]) => (
              <div key={key} className="cost-row">
                <span className="cost-label">{key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}</span>
                <span className="cost-value">{formatCost(val)}</span>
              </div>
            ))}
            <div className="cost-row">
              <span className="cost-label">Total Cost</span>
              <span className="cost-value" style={{ color: 'var(--primary)' }}>
                {formatCost(costData.spot_cost?.total_cost)}
              </span>
            </div>
            <div className="cost-row">
              <span className="cost-label">Cost per MT</span>
              <span className="cost-value">${costData.spot_cost?.cost_per_mt?.toFixed(1)}</span>
            </div>
          </div>
        </div>

        <div className="card">
          <div className="card-header">
            <div className="card-title">Cost Comparison</div>
          </div>
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--hairline)" strokeOpacity={0.5} />
              <XAxis dataKey="name" stroke="var(--ink-tertiary)" tick={{ fontSize: 11 }} />
              <YAxis
                stroke="var(--ink-tertiary)"
                tick={{ fontSize: 11 }}
                tickFormatter={v => `$${v.toFixed(1)}M`}
              />
              <Tooltip
              contentStyle={{
                background: 'var(--surface-1)',
                border: '1px solid var(--hairline)',
                borderRadius: 'var(--radius-sm)',
                fontSize: '12px',
                boxShadow: 'var(--shadow-md)',
                padding: '8px 12px'
              }}
                formatter={(value) => [`$${value.toFixed(2)}M`, 'Total Cost']}
              />
              <Bar dataKey="cost" radius={[4, 4, 0, 0]} barSize={36}>
                {chartData.map((entry, i) => (
                  <Cell
                    key={i}
                    fill={entry.cost * 1000000 === lowestCost ? 'var(--primary)' : 'var(--surface-4)'}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="card" style={{ marginTop: '20px' }}>
        <div className="card-header">
          <div className="card-title">Contract Options</div>
          <div className="card-subtitle">
            Spot vs multi-voyage contracts
            {costData.fleet?.num_ships > 1 ? ` · fleet totals (${costData.fleet.num_ships} ships)` : ''}
          </div>
        </div>
        <table className="contract-table">
          <thead>
            <tr>
              <th>Type</th>
              <th>Voyages</th>
              <th>Freight Rate</th>
              <th>Total Cost</th>
              <th>Cost / MT</th>
              <th>Savings vs Spot</th>
              <th>Savings %</th>
            </tr>
          </thead>
          <tbody>
            {costData.comparison?.map((c, i) => (
              <tr key={i} className={c.total_cost === lowestCost ? 'recommended' : ''}>
                <td>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <span style={{ textTransform: 'capitalize', fontWeight: 500 }}>
                      {c.type?.replace('_', ' ')}
                    </span>
                    {c.total_cost === lowestCost && (
                      <span className="badge badge-active">BEST</span>
                    )}
                  </div>
                </td>
                <td>{c.voyages}</td>
                <td style={{ fontFeatureSettings: 'tnum' }}>${c.freight_rate?.toFixed(2)}</td>
                <td style={{ fontFeatureSettings: 'tnum', fontWeight: 500 }}>
                  {formatCost(c.total_cost)}
                </td>
                <td style={{ fontFeatureSettings: 'tnum' }}>${c.cost_per_mt?.toFixed(1)}</td>
                <td style={{ fontFeatureSettings: 'tnum', color: c.savings_vs_spot > 0 ? 'var(--success)' : 'var(--ink-subtle)' }}>
                  {c.savings_vs_spot > 0 ? formatCost(c.savings_vs_spot) : '--'}
                </td>
                <td style={{ fontFeatureSettings: 'tnum', color: c.savings_pct > 0 ? 'var(--success)' : 'var(--ink-subtle)' }}>
                  {c.savings_pct > 0 ? `${c.savings_pct}%` : '--'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default ContractComparison;
