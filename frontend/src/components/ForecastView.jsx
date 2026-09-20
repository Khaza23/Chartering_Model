import React from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Area, AreaChart } from 'recharts';
import { ForecastSkeleton } from './Skeleton';

const ForecastView = ({ forecast, loading }) => {
  if (loading) {
    return <ForecastSkeleton />;
  }

  if (!forecast) {
    return (
      <div className="empty-state">
        <div className="empty-state-icon">📊</div>
        <div className="empty-state-text">No forecast data</div>
        <div className="empty-state-sub">Run an analysis from the Decision tab first</div>
      </div>
    );
  }

  const chartData = forecast.forecast_range?.map(f => ({
    date: f.date,
    value: f.value,
    lower: f.lower,
    upper: f.upper,
    confidence: f.confidence
  })) || [];

  const trendColor = forecast.forecast?.trend === 'rising' ? 'var(--danger)' :
    forecast.forecast?.trend === 'falling' ? 'var(--success)' : 'var(--ink-subtle)';

  const trendIcon = forecast.forecast?.trend === 'rising' ? '↑' :
    forecast.forecast?.trend === 'falling' ? '↓' : '→';

  return (
    <div>
      <div className="metric-row">
        <div className="metric-card">
          <div className="metric-label">Current Rate</div>
          <div className="metric-value">
            ${forecast.current_rate?.toFixed(1)}<span className="metric-unit">/MT</span>
          </div>
        </div>
        <div className="metric-card">
          <div className="metric-label">Forecast (30d)</div>
          <div className="metric-value" style={{ color: trendColor }}>
            ${forecast.forecast?.value?.toFixed(1)}<span className="metric-unit">/MT</span>
          </div>
        </div>
        <div className="metric-card">
          <div className="metric-label">Expected Range</div>
          <div className="metric-value" style={{ fontSize: '16px' }}>
            ${forecast.forecast?.lower_bound?.toFixed(1)} – ${forecast.forecast?.upper_bound?.toFixed(1)}
          </div>
        </div>
        <div className="metric-card">
          <div className="metric-label">Confidence</div>
          <div className="metric-value">
            {(forecast.forecast?.confidence * 100).toFixed(0)}%
          </div>
          <div className="confidence-bar" style={{ marginTop: '6px' }}>
            <div className="confidence-track">
              <div className="confidence-fill" style={{
                width: `${forecast.forecast?.confidence * 100}%`,
                background: forecast.forecast?.confidence > 0.7 ? 'var(--success)' : 'var(--warning)'
              }} />
            </div>
          </div>
        </div>
        <div className="metric-card">
          <div className="metric-label">Market Trend</div>
          <div className="metric-value" style={{ color: trendColor, fontSize: '18px' }}>
            {trendIcon} {forecast.forecast?.trend?.toUpperCase()}
          </div>
        </div>
      </div>

      <div className="forecast-chart">
        <div className="card-header">
          <div className="card-title">Freight Rate Forecast</div>
          <div className="card-subtitle">
            {forecast.route} · {forecast.vessel_class} · Ensemble Model
          </div>
        </div>
        <ResponsiveContainer width="100%" height={350}>
          <AreaChart data={chartData}>
            <defs>
              <linearGradient id="confidenceGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="var(--primary)" stopOpacity={0.08} />
                <stop offset="95%" stopColor="var(--primary)" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--hairline)" strokeOpacity={0.5} />
            <XAxis
              dataKey="date"
              stroke="var(--ink-tertiary)"
              tick={{ fontSize: 11 }}
              tickFormatter={v => {
                const d = new Date(v);
                return `${d.getMonth() + 1}/${d.getDate()}`;
              }}
            />
            <YAxis
              stroke="var(--ink-tertiary)"
              tick={{ fontSize: 11 }}
              tickFormatter={v => `$${v}`}
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
              formatter={(value, name) => {
                if (name === 'upper') return [`$${value.toFixed(1)}`, 'Upper Bound'];
                if (name === 'lower') return [`$${value.toFixed(1)}`, 'Lower Bound'];
                return [`$${value.toFixed(1)}`, 'Forecast'];
              }}
            />
            <Area
              type="monotone"
              dataKey="upper"
              stroke="transparent"
              fill="transparent"
            />
            <Area
              type="monotone"
              dataKey="lower"
              stroke="transparent"
              fill="url(#confidenceGrad)"
            />
            <Line
              type="monotone"
              dataKey="value"
              stroke="var(--primary)"
              strokeWidth={2}
              dot={false}
              name="Forecast"
            />
            <Line
              type="monotone"
              dataKey="upper"
              stroke="var(--primary)"
              strokeWidth={1}
              strokeDasharray="4 4"
              dot={false}
              opacity={0.4}
              name="Upper"
            />
            <Line
              type="monotone"
              dataKey="lower"
              stroke="var(--primary)"
              strokeWidth={1}
              strokeDasharray="4 4"
              dot={false}
              opacity={0.4}
              name="Lower"
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      <div className="two-col" style={{ marginTop: '20px' }}>
        <div className="card">
          <div className="card-header">
            <div className="card-title">Model Information</div>
          </div>
          <div className="cost-breakdown">
            <div className="cost-row">
              <span className="cost-label">Model Type</span>
              <span className="cost-value">Ensemble (Prophet + XGBoost)</span>
            </div>
            <div className="cost-row">
              <span className="cost-label">Prophet Weight</span>
              <span className="cost-value">{(forecast.model_info?.prophet_weight * 100).toFixed(0)}%</span>
            </div>
            <div className="cost-row">
              <span className="cost-label">XGBoost Weight</span>
              <span className="cost-value">{(forecast.model_info?.xgboost_weight * 100).toFixed(0)}%</span>
            </div>
            <div className="cost-row">
              <span className="cost-label">Training Points</span>
              <span className="cost-value">{forecast.model_info?.training_points?.toLocaleString()}</span>
            </div>
          </div>
        </div>
        <div className="card">
          <div className="card-header">
            <div className="card-title">Market Indicators</div>
          </div>
          <div className="cost-breakdown">
            <div className="cost-row">
              <span className="cost-label">Volatility (30d)</span>
              <span className="cost-value">{(forecast.volatility * 100).toFixed(1)}%</span>
            </div>
            <div className="cost-row">
              <span className="cost-label">Confidence Level</span>
              <span className="cost-value">{(forecast.forecast?.confidence * 100).toFixed(0)}%</span>
            </div>
            <div className="cost-row">
              <span className="cost-label">Direction</span>
              <span className="cost-value" style={{ color: trendColor }}>
                {forecast.forecast?.trend?.toUpperCase()}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ForecastView;
