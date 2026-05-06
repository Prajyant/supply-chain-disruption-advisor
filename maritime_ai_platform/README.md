# Maritime AI Risk Intelligence Platform

Real-time maritime vessel tracking and AI-powered risk analysis desktop application.

## Features

- **Live World Map** — Interactive Leaflet.js map with vessel markers color-coded by risk level (GREEN/ORANGE/RED)
- **AIS Vessel Tracking** — Real-time data from AISHub or MarineTraffic with 5-minute polling
- **AI Risk Analysis** — AWS Bedrock (Claude 3.5 Sonnet) powered maritime intelligence
- **Danger Zone Monitoring** — Red Sea, Gulf of Aden, Strait of Hormuz, Gulf of Guinea, South China Sea
- **Alert System** — Automated alerts for high risk, AIS silence, speed anomalies, danger zone entry
- **Analytics** — Speed history, risk trends, traffic density, risk distribution charts
- **Modern Dark UI** — PyQt5 desktop application with responsive split-panel layout

## Architecture

```
maritime_ai_platform/
├── main.py              # Application entry point
├── config/              # Configuration management
│   └── settings.py      # Dataclass-based config with .env support
├── ui/                  # PyQt5 user interface
│   ├── main_window.py   # Main window orchestrator
│   ├── vessel_sidebar.py # Search, filters, vessel list
│   ├── detail_panel.py  # Vessel details + AI analysis
│   ├── alert_panel.py   # Alert notifications
│   ├── analytics_panel.py # Fleet analytics
│   └── styles.py        # Dark theme stylesheet
├── ai/                  # AI and risk engines
│   ├── bedrock_engine.py # AWS Bedrock integration
│   ├── risk_engine.py   # Weighted risk scoring
│   └── alert_engine.py  # Alert generation
├── ais/                 # AIS data providers
│   ├── provider_base.py # Abstract provider interface
│   ├── aishub_provider.py # AISHub API
│   ├── marinetraffic_provider.py # MarineTraffic API
│   ├── demo_provider.py # Demo data for testing
│   └── ais_engine.py   # Threaded data engine
├── map/                 # Map visualization
│   └── map_widget.py   # Leaflet.js in QWebEngineView
├── analytics/           # Charts and analytics
│   └── charts.py       # Matplotlib chart widgets
├── database/            # Persistence layer
│   └── db_manager.py   # SQLite with thread safety
├── logs/                # Application logs
├── cache/               # Data cache
└── requirements.txt     # Python dependencies
```

## Quick Start

### Prerequisites

- Python 3.12+
- pip

### Installation

```bash
cd maritime_ai_platform
pip install -r requirements.txt
```

### Configuration

1. Copy the example environment file:
```bash
cp .env.example .env
```

2. Edit `.env` with your credentials (optional — app runs in demo mode without them):
```
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
AWS_REGION=us-east-1
AIS_API_KEY=your_ais_key
AIS_PROVIDER=aishub
```

### Run

```bash
python main.py
```

The application starts immediately in **demo mode** if no API keys are configured, displaying 20 simulated vessels across global shipping lanes.

## AWS Bedrock Setup

1. Create an AWS account and enable Bedrock in your region
2. Request access to Claude 3.5 Sonnet model in the Bedrock console
3. Create an IAM user with `bedrock:InvokeModel` permission
4. Set `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` in your `.env`

Required IAM policy:
```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": "bedrock:InvokeModel",
            "Resource": "arn:aws:bedrock:*::foundation-model/anthropic.claude-3-5-sonnet-*"
        }
    ]
}
```

Without AWS credentials, the platform uses a rule-based fallback engine that still provides geographic risk scoring and behavioral analysis.

## AIS API Setup

### AISHub
1. Register at https://www.aishub.net/
2. Share your AIS data or purchase a subscription
3. Get your API username/key
4. Set `AIS_API_KEY` and `AIS_PROVIDER=aishub` in `.env`

### MarineTraffic
1. Register at https://www.marinetraffic.com/en/ais-api-services
2. Subscribe to a vessel tracking plan
3. Get your API key
4. Set `AIS_API_KEY` and `AIS_PROVIDER=marinetraffic` in `.env`

### Demo Mode
Without an AIS API key, the application generates 20 realistic vessels positioned across major shipping lanes and danger zones, with simulated movement updates every 5 minutes.

## Risk Scoring

The platform uses a weighted risk scoring system (0-100):

| Score | Level | Color |
|-------|-------|-------|
| 0-30 | LOW | Green |
| 31-70 | MEDIUM | Orange |
| 71-100 | HIGH | Red |

Risk factors:
- **Geographic** — Proximity to danger zones (15-30 points each)
- **Speed anomaly** — Deviation from historical average (8-15 points)
- **AIS silence** — Signal gaps beyond threshold (8-25 points)
- **Route deviation** — Erratic course changes (8-15 points)
- **Behavioral** — Type-specific risk indicators (3-10 points)

## Keyboard Shortcuts

- `Ctrl+R` — Manual refresh
- `Ctrl+Q` — Quit application

## Logging

Logs are written to `logs/maritime_ai_YYYYMMDD.log` with daily rotation. Sensitive data (API keys, credentials) is never logged.

## License

MIT
