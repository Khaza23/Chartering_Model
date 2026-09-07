"""Free ($0) live-data connectors. Each fetch() returns a DataFrame matching
the existing DB schema. All connectors fail soft (return empty DF) when keys
are missing or quotas hit — sync_service keeps last DB values as fallback."""

from .base import http_get, parse_csv_rows
from .freight_stooq import fetch_bdi_daily, to_route_rates
from .commodities_fred import fetch_commodities
from .bunker_eia import fetch_bunker_trend

__all__ = [
    "http_get",
    "parse_csv_rows",
    "fetch_bdi_daily",
    "to_route_rates",
    "fetch_commodities",
    "fetch_bunker_trend",
]
