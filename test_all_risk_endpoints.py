"""Test all 20 risk-related endpoints."""
import requests
import json
import time

BASE = "http://localhost:8000"
PASS = 0
FAIL = 0
RESULTS = []


def test(name, method, path, **kwargs):
    global PASS, FAIL
    timeout = kwargs.pop("timeout", 30)
    try:
        r = getattr(requests, method)(f"{BASE}{path}", timeout=timeout, **kwargs)
        status = r.status_code
        ok = status in (200, 201)
        if ok:
            PASS += 1
            RESULTS.append(f"  ✓ {name} [{status}]")
        else:
            FAIL += 1
            detail = r.text[:150] if r.text else ""
            RESULTS.append(f"  ✗ {name} [{status}] {detail}")
    except Exception as e:
        FAIL += 1
        RESULTS.append(f"  ✗ {name} [ERROR] {str(e)[:100]}")


# Sample shipment for POST endpoints
SAMPLE_SHIPMENT = {
    "shipment_id": "SHP-2001",
    "supplier": "CMA CGM Shipping",
    "origin": "Shanghai",
    "destination": "Los Angeles",
    "route_nodes": ["Shanghai", "Pacific Ocean", "Los Angeles"],
    "transport_mode": "sea",
    "material": "electronics components",
    "quantity": 1200,
    "lead_time_days": 22,
    "inventory_days_cover": 4,
    "supplier_delay_count": 1,
    "priority": "3",
    "declared_value_usd": 350000,
    "mmsi": "256995000",
    "vessel_name": "CMA CGM SHANGHAI",
}

print("=" * 60)
print("  RISK ENDPOINT TEST SUITE")
print("=" * 60)

# ── Core Risk Endpoints ──
print("\n[1] Core Risk Endpoints")
test("GET /risks", "get", "/risks")
test("GET /risks/{id}", "get", "/risks/RISK-001")

# ── Shipment Risk Endpoints ──
print("\n[2] Shipment Risk Endpoints")
test("GET /shipments/risk-summary", "get", "/shipments/risk-summary")
test("POST /shipments/risk-score", "post", "/shipments/risk-score", json={
    "shipment": SAMPLE_SHIPMENT,
    "use_live_intelligence": False,
})
test("POST /shipments/risk-advice", "post", "/shipments/risk-advice", json={
    "shipment": SAMPLE_SHIPMENT,
    "use_live_intelligence": False,
    "question": "What are the main risks?",
}, timeout=60)
test("POST /shipments/resolution-package", "post", "/shipments/resolution-package", json={
    "shipment": SAMPLE_SHIPMENT,
    "use_live_intelligence": False,
    "question": "Generate resolution",
}, timeout=60)
test("POST /shipments/preload", "post", "/shipments/preload", json=[SAMPLE_SHIPMENT])
test("GET /shipments/{id}/preloaded", "get", "/shipments/SHP-2001/preloaded")

# ── Maritime Intelligence Risk Endpoints ──
print("\n[3] Maritime Intelligence Endpoints")
test("GET /maritime/route-distance", "get", "/maritime/route-distance",
     params={"origin": "rotterdam", "destination": "southampton"})
test("GET /maritime/route-deviation", "get", "/maritime/route-deviation",
     params={"vessel_lat": 51.5, "vessel_lon": 2.0, "origin": "rotterdam", "destination": "southampton"})
test("GET /maritime/vessel-registry/{imo}", "get", "/maritime/vessel-registry/9811000")
test("GET /maritime/sanctions/vessel/{imo}", "get", "/maritime/sanctions/vessel/9811000",
     params={"vessel_name": "EVER GIVEN"})
test("GET /maritime/sanctions/entity/{name}", "get", "/maritime/sanctions/entity/Evergreen Marine")
test("GET /maritime/sanctions/route", "get", "/maritime/sanctions/route",
     params={"countries": "China,Singapore,Netherlands"})
test("GET /maritime/tariffs", "get", "/maritime/tariffs",
     params={"origin_country": "CHN", "destination_country": "USA", "product_category": "electronics"})
test("GET /maritime/port-congestion/{port}", "get", "/maritime/port-congestion/rotterdam")
test("GET /maritime/port-congestion (all)", "get", "/maritime/port-congestion")

# ── Graph Risk Endpoints ──
print("\n[4] Graph Risk Endpoints")
test("POST /graph/propagate", "post", "/graph/propagate")
test("POST /graph/score-nodes", "post", "/graph/score-nodes")

# ── Agent Risk Endpoints ──
print("\n[5] Agent Risk Endpoints")
test("POST /agents/strands/shipment-risk", "post", "/agents/strands/shipment-risk", json={
    "shipment": SAMPLE_SHIPMENT,
    "question": "Assess risk",
    "use_live_intelligence": False,
    "prefer_strands_sdk": False,
}, timeout=60)

# ── Print Results ──
print("\n" + "=" * 60)
print("  RESULTS")
print("=" * 60)
for r in RESULTS:
    print(r)
print(f"\n  TOTAL: {PASS} passed, {FAIL} failed out of {PASS + FAIL}")
print("=" * 60)
