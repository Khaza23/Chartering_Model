import urllib.request
import json
import time

base_url = 'http://localhost:8000/api'
from datetime import date, timedelta
today = date.today()
params = {
    'cargo_quantity': 75000,
    'origin': 'Australia',
    'destination': 'Paradip',
    'laycan_start': (today + timedelta(days=3)).strftime('%Y-%m-%d'),
    'laycan_end': (today + timedelta(days=13)).strftime('%Y-%m-%d'),
    'required_voyages': 6,
    'current_freight_rate': 22.0
}

def post(endpoint, payload):
    req = urllib.request.Request(
        f'{base_url}/{endpoint}',
        data=json.dumps(payload).encode('utf-8'),
        headers={'Content-Type': 'application/json'}
    )
    t0 = time.time()
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode('utf-8'))
        print(f"  [{endpoint}] completed in {time.time()-t0:.2f}s")
        return data

print("Testing pipeline endpoints:")
feas = post('feasibility', params)
print(f"  -> Feasible vessels: {feas['summary']['feasible_count']}")

cost = post('cost', {
    'freight_rate': params['current_freight_rate'],
    'cargo_quantity': params['cargo_quantity'],
    'vessel_id': 1,
    'port_name': params['destination'],
    'origin': params['origin']
})
print(f"  -> Spot cost: ${cost['spot_cost']['total_cost']:,.2f}")

forecast = post('forecast', {
    'route': f"{params['origin']}-{params['destination']}",
    'vessel_class': 'panamax',
    'forecast_days': 30
})
print(f"  -> Forecast 30-day: ${forecast['forecast']['value']:.2f}/ton ({forecast['forecast']['trend']})")

opt = post('optimize', params)
print(f"  -> Action: {opt['action']}, Contract: {opt['contract_type']}, Expected Savings: ${opt['expected_savings']:,.2f}")

print("Testing scenario endpoint:")
scenario = post('scenario', {
    'base_params': params,
    'freight_change_pct': 10,
    'bunker_change_pct': -5,
    'congestion_change': 15,
    'delay_change_hours': 24
})
print(f"  -> Scenario cost change: ${scenario['impact']['cost_change']:,.2f} ({scenario['impact']['cost_change_pct']}%)")

print("All endpoints passed successfully!")
