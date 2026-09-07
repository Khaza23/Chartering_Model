import React from 'react';

// Linear DESIGN.md: status-badge = surface-2 bg, ink-muted caption,
// pill 9999px, padding 2px 8px. Live dot uses semantic-success only.
const LABELS = {
  freight: 'Freight · BDI proxy',
  bunker: 'Bunker · EIA trend',
  commodities: 'Commodities · FRED',
  congestion: 'Congestion · AIS',
};

const TOOLTIPS = {
  freight: 'Route $/t = live Baltic Dry Index × route factor (proxy, not a direct fixture).',
  bunker: 'Port VLSFO/MGO = EIA fuel trend anchored to last stored port price + port premium.',
  commodities: 'Coal/iron ore monthly via FRED (2–3 wk lag), forward-filled to daily.',
  congestion: 'AIS-derived waiting count in tight port boxes; proxy, not a commercial fixture list.',
};

const DataStatus = ({ status, compact = false }) => {
  if (!status || !status.datasets) return null;
  const entries = Object.entries(status.datasets);
  const liveCount = entries.filter(([, v]) => v && !v.stale).length;
  const anyStale = entries.some(([, v]) => v && v.stale);

  return (
    <div className="data-status" title="Live data freshness per dataset">
      <span className="status-badge" title={`${liveCount}/${entries.length} datasets live`}>
        <span className="status-dot" style={{ background: anyStale ? 'var(--ink-subtle)' : 'var(--success)' }} />
        {anyStale ? `Synthetic · ${liveCount}/${entries.length} live` : `Live · ${liveCount}/${entries.length}`}
      </span>
      {!compact && (
        <div className="data-status-row">
          {entries.map(([key, v]) => (
            <span
              key={key}
              className="status-badge"
              title={`${LABELS[key] || key}. ${TOOLTIPS[key] || ''} ${v.last_fetched_at ? `Updated ${v.last_fetched_at}.` : 'Using seeded baseline.'}`}
            >
              <span
                className="status-dot"
                style={{ background: v && !v.stale ? 'var(--success)' : 'var(--ink-tertiary)' }}
              />
              {key}
            </span>
          ))}
        </div>
      )}
    </div>
  );
};

export default DataStatus;
