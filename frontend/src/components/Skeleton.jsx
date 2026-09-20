import React from 'react';

/* Base shimmer block. Width/height via style prop; shape via className. */
export const Sk = ({ className = '', style = {} }) => (
  <div className={`sk ${className}`} style={style} aria-hidden="true" />
);

const Shell = ({ label = 'Loading…', children }) => (
  <div role="status" aria-label={label} aria-busy="true">
    {children}
  </div>
);

const MetricCards = ({ count = 3 }) => (
  <div className="metric-row">
    {Array.from({ length: count }).map((_, i) => (
      <div key={i} className="metric-card">
        <Sk className="sk-label" style={{ width: '40%' }} />
        <Sk className="sk-value" style={{ width: '70%' }} />
        <Sk className="sk-line" style={{ width: '55%' }} />
      </div>
    ))}
  </div>
);

const TableRows = ({ rows = 5, cols = 4 }) => (
  <div className="sk-table">
    <div className="sk-table-head">
      {Array.from({ length: cols }).map((_, i) => (
        <Sk key={i} className="sk-line" style={{ width: `${55 + ((i * 13) % 30)}%` }} />
      ))}
    </div>
    {Array.from({ length: rows }).map((_, r) => (
      <div key={r} className="sk-table-row">
        {Array.from({ length: cols }).map((_, c) => (
          <Sk key={c} className="sk-line" style={{ width: `${45 + ((r * 17 + c * 11) % 45)}%` }} />
        ))}
      </div>
    ))}
  </div>
);

/* Decision tab: banner + metric cards + two cards (matches real layout). */
export const DecisionSkeleton = () => (
  <Shell label="Loading recommendation…">
    <div className="recommendation-banner">
      <Sk className="sk-label" style={{ width: '120px' }} />
      <Sk className="sk-title" style={{ width: '62%' }} />
      <Sk className="sk-line" style={{ width: '38%' }} />
      <div className="rec-meta">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="rec-meta-item">
            <Sk className="sk-label" style={{ width: '64px' }} />
            <Sk className="sk-value-sm" style={{ width: '72px' }} />
          </div>
        ))}
      </div>
    </div>
    <MetricCards count={3} />
    <div className="two-col">
      {[0, 1].map((i) => (
        <div key={i} className="card">
          <Sk className="sk-title-sm" style={{ width: '45%' }} />
          <Sk className="sk-line" />
          <Sk className="sk-line" style={{ width: '88%' }} />
          <Sk className="sk-line" style={{ width: '70%' }} />
        </div>
      ))}
    </div>
  </Shell>
);

/* Forecast tab: metric cards + chart + two cards. */
export const ForecastSkeleton = () => (
  <Shell label="Loading forecast…">
    <MetricCards count={5} />
    <div className="forecast-chart">
      <Sk className="sk-title-sm" style={{ width: '220px' }} />
      <Sk className="sk-line" style={{ width: '300px' }} />
      <Sk className="sk-chart" />
    </div>
    <div className="two-col" style={{ marginTop: '20px' }}>
      {[0, 1].map((i) => (
        <div key={i} className="card">
          <Sk className="sk-title-sm" style={{ width: '50%' }} />
          <Sk className="sk-line" />
          <Sk className="sk-line" style={{ width: '80%' }} />
          <Sk className="sk-line" style={{ width: '65%' }} />
        </div>
      ))}
    </div>
  </Shell>
);

/* Vessels tab: metric cards + wide table card. */
export const VesselsSkeleton = () => (
  <Shell label="Loading vessels…">
    <MetricCards count={4} />
    <div className="card">
      <Sk className="sk-title-sm" style={{ width: '200px' }} />
      <Sk className="sk-line" style={{ width: '85%' }} />
      <TableRows rows={6} cols={5} />
    </div>
  </Shell>
);

/* Contracts tab: two cards (breakdown + chart) + options table. */
export const ContractsSkeleton = () => (
  <Shell label="Loading cost comparison…">
    <div className="two-col">
      <div className="card">
        <Sk className="sk-title-sm" style={{ width: '55%' }} />
        <Sk className="sk-line" />
        <Sk className="sk-line" style={{ width: '90%' }} />
        <Sk className="sk-line" style={{ width: '75%' }} />
        <Sk className="sk-line" style={{ width: '85%' }} />
      </div>
      <div className="card">
        <Sk className="sk-title-sm" style={{ width: '45%' }} />
        <Sk className="sk-chart-sm" />
      </div>
    </div>
    <div className="card" style={{ marginTop: '20px' }}>
      <Sk className="sk-title-sm" style={{ width: '180px' }} />
      <TableRows rows={4} cols={5} />
    </div>
  </Shell>
);

/* Timing tab: verdict banner + options table. */
export const TimingSkeleton = () => (
  <Shell label="Assessing timing…">
    <div className="recommendation-banner">
      <Sk className="sk-label" style={{ width: '100px' }} />
      <Sk className="sk-title" style={{ width: '48%' }} />
      <div className="rec-meta">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="rec-meta-item">
            <Sk className="sk-label" style={{ width: '64px' }} />
            <Sk className="sk-value-sm" style={{ width: '72px' }} />
          </div>
        ))}
      </div>
    </div>
    <div className="card">
      <Sk className="sk-title-sm" style={{ width: '190px' }} />
      <TableRows rows={6} cols={5} />
    </div>
  </Shell>
);

/* What-If tab: base vs scenario cards. */
export const ScenarioSkeleton = () => (
  <Shell label="Running scenario…">
    <div className="two-col">
      {[0, 1].map((i) => (
        <div key={i} className="card">
          <Sk className="sk-title-sm" style={{ width: '40%' }} />
          <Sk className="sk-line" />
          <Sk className="sk-line" style={{ width: '85%' }} />
          <Sk className="sk-line" style={{ width: '70%' }} />
          <Sk className="sk-line" style={{ width: '78%' }} />
        </div>
      ))}
    </div>
  </Shell>
);

export default Sk;
