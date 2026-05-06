# Vessel Tracking System

## Overview

IMO-based vessel route tracking integrated into the Supply Chain Disruption Advisor.
Monitors up to 60 vessels from a CSV watchlist, detects anomalies (AIS silence, speed
drops, danger zone transits), and feeds intelligence into the existing risk engine,
digital twin, chat advisor, and playbook system.

## Architecture

```
watchlist.csv → AIS Engine → Vessel Database (SQLite)
                    ↓                    ↓
              Anomaly Detection    Route History Storage
                    ↓                    ↓
         ┌─────────┼─────────┐          ↓
         ↓         ↓         ↓     API Endpoints
    WebSocket   Risk Engine  Playbook    ↓
    Alerts      Integration  Triggers  Frontend
         ↓         ↓         ↓     (Leaflet Map)
       Frontend  Digital Twin  Automated
       Alerts    Graph Update  Response
```

## Quick Start

### 1. Configure Provider

Edit `.env`:
```bash
# Use demo mode (no API key needed):
AIS_PROVIDER=demo

# Or use a real provider:
AIS_PROVIDER=marinetraffic  # or: aishub
AIS_API_KEY=your-api-key-here
```

### 2. Create Watchlist

Copy the example and customize:
```bash
cp watchlist_example.csv watchlist.csv
```

Edit `watchlist.csv`:
```csv
imo_number,vessel_name,linked_supplier,linked_shipment_id,notes
9811000,EVER GIVEN,Supplier_A,SHP-001,Critical Suez route
9461867,MSC OSCAR,Supplier_B,SHP-005,Gulf route monitoring
```

### 3. Find IMO Numbers

Use the CLI utility:
```bash
python find_imo.py "EVER GIVEN"
python find_imo.py "MSC"
python find_imo.py --imo 9349028
```

### 4. Start the Application

```bash
uvicorn app.main:app --reload
```

The vessel tracking worker starts automatically and begins polling.

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `AIS_PROVIDER` | `demo` | Provider: `aishub`, `marinetraffic`, `demo` |
| `AIS_API_KEY` | (none) | API key for the selected provider |
| `WATCHLIST_CSV_PATH` | `./watchlist.csv` | Path to the vessel watchlist |
| `VESSEL_POLL_INTERVAL_SECONDS` | `300` | Polling interval (5 minutes) |
| `VESSEL_SILENCE_THRESHOLD_HOURS` | `6` | Hours before flagging AIS silence |
| `VESSEL_STALE_THRESHOLD_HOURS` | `1` | Hours before showing stale status |
| `VESSEL_HISTORY_RETENTION_DAYS` | `90` | Auto-purge positions older than this |
| `VESSEL_IDENTITY_CACHE_DAYS` | `30` | Re-resolve vessel identity after this |

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/vessels/watchlist` | All watched vessels with status |
| GET | `/vessels/fleet-status` | Fleet summary counts |
| GET | `/vessels/{imo}/status` | Real-time vessel status |
| GET | `/vessels/{imo}/track` | Route history (supports `?hours=`, `?days=`, `?from=&to=`) |
| GET | `/vessels/resolve/{imo}` | Resolve IMO to full identity |
| GET | `/vessels/search?q=name` | Search vessels by name |
| GET | `/vessels/danger-zones` | Zone definitions + vessels inside |
| POST | `/vessels/watchlist/reload` | Force CSV reload |
| POST | `/vessels/{imo}/link` | Link vessel to supplier/shipment |

## Data Flow

1. **Watchlist CSV** → Read on startup and hot-reloaded on each poll cycle
2. **AIS Provider** → Fetches current position for each IMO (staggered requests)
3. **Vessel Database** → Stores positions in `vessel_positions` table, caches identity
4. **Anomaly Detection** → Checks for AIS silence, speed anomalies, danger zone entry
5. **WebSocket** → Broadcasts position updates and anomaly alerts to frontend
6. **Risk Engine** → Vessel anomalies generate risk events (source: "vessel_tracking")
7. **Chat Advisor** → Fleet status added to global context for natural language queries
8. **Playbook Engine** → Anomalies can trigger automated response playbooks

## Danger Zones

Defined in `app/ingestion/ais/danger_zones.json`:
- Red Sea / Bab-el-Mandeb (weight: 25)
- Gulf of Aden (weight: 30)
- Strait of Hormuz (weight: 20)
- Gulf of Guinea (weight: 28)
- South China Sea (weight: 15)
- Malacca Strait (weight: 18)
- Somali Basin (weight: 30)

## Demo Mode

When `AIS_PROVIDER=demo` or no API key is set:
- Reads `watchlist.csv` and simulates realistic data for those IMOs
- If CSV is empty: generates 20 default vessels on major shipping lanes
- Generates 7 days of route history on first startup
- Simulates movement every 5 minutes with realistic course changes
- Periodically simulates anomalies (AIS gaps, speed drops, danger zone transits)
- Full alert/risk/playbook pipeline works in demo mode

## Frontend

Access the vessel tracking page at `/vessel-tracking`:
- Full-width Leaflet map with vessel markers and danger zone overlays
- Sidebar watchlist with status indicators and search/filter
- Route polylines with time-range selector (24h/7d/30d)
- Fleet statistics bar
- Real-time WebSocket updates

## Integration Points

### Risk Engine
Vessel anomalies are added as signals to the existing risk scoring.
They appear in `GET /risks` with `source: "vessel_tracking"`.

### Digital Twin
When a vessel linked to a supplier goes anomalous, that supplier node's
risk score is updated and risk propagates downstream.

### Chat Advisor
Users can ask: "Where is EVER GIVEN?", "Which vessels are delayed?",
"Show me vessels in the Red Sea". Fleet status is in the global context.

### Playbook Engine
Trigger conditions: `vessel_ais_silent`, `vessel_in_danger_zone`,
`vessel_speed_anomaly`, `vessel_eta_delay`.

## Cleanup Note

The `maritime_ai_platform/` folder can be safely deleted after confirming
the integration is working correctly. All relevant logic has been extracted
and adapted into `app/ingestion/ais/` and the frontend components.

## Files Added

### Backend
- `app/ingestion/ais/__init__.py` — Package init
- `app/ingestion/ais/provider_base.py` — Abstract async provider interface
- `app/ingestion/ais/aishub_provider.py` — AISHub async provider
- `app/ingestion/ais/marinetraffic_provider.py` — MarineTraffic async provider
- `app/ingestion/ais/demo_provider.py` — Demo data generator
- `app/ingestion/ais/ais_engine.py` — Main engine with watchlist, DB, anomaly detection
- `app/ingestion/ais/vessel_worker.py` — Background worker + app integration
- `app/ingestion/ais/danger_zones.json` — GeoJSON danger zone definitions
- `app/api/vessel_routes.py` — FastAPI vessel endpoints

### Frontend
- `frontend/src/types/vessel.ts` — TypeScript interfaces
- `frontend/src/store/vesselStore.ts` — Zustand state management
- `frontend/src/services/vesselApi.ts` — API client
- `frontend/src/components/VesselWatchlist.tsx` — Sidebar vessel list
- `frontend/src/components/VesselRouteLayer.tsx` — Route polylines on map
- `frontend/src/components/VesselStatusCard.tsx` — Vessel detail card
- `frontend/src/components/VesselAlertBanner.tsx` — Anomaly alert banner
- `frontend/src/components/DangerZoneOverlay.tsx` — Map danger zone overlays
- `frontend/src/components/WatchlistManager.tsx` — Search + add to watchlist UI
- `frontend/src/pages/VesselTracking.tsx` — Full-page tracking view

### Configuration
- `watchlist.csv` — Empty template with headers
- `watchlist_example.csv` — 10 real vessel IMOs with example links
- `find_imo.py` — CLI utility for IMO lookup
- `VESSEL_TRACKING_README.md` — This file

### Modified
- `app/main.py` — Added vessel worker startup/shutdown + vessel router
- `app/core/config.py` — Added vessel tracking settings
- `app/api/routes.py` — (unchanged, new routes in separate file)
- `requirements.txt` — Added httpx, shapely
- `.env.example` — Added vessel tracking variables
- `frontend/src/App.tsx` — Added VesselTracking route
