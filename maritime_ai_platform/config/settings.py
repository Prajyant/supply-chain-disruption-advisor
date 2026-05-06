"""
Configuration manager for Maritime AI Risk Intelligence Platform.
Handles environment variables, defaults, and runtime configuration.
"""

import os
import json
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

try:
    from dotenv import load_dotenv
    # Load .env from the package directory
    _env_path = Path(__file__).resolve().parent.parent / ".env"
    load_dotenv(_env_path)
except ImportError:
    pass

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
LOGS_DIR = BASE_DIR / "logs"
CACHE_DIR = BASE_DIR / "cache"
DB_DIR = BASE_DIR / "database"
ASSETS_DIR = BASE_DIR / "assets"

for d in [LOGS_DIR, CACHE_DIR, DB_DIR, ASSETS_DIR]:
    d.mkdir(parents=True, exist_ok=True)


@dataclass
class AWSConfig:
    access_key_id: str = ""
    secret_access_key: str = ""
    session_token: str = ""
    region: str = "us-east-1"
    bedrock_model_id: str = "anthropic.claude-3-5-sonnet-20241022-v2:0"
    max_tokens: int = 2048
    temperature: float = 0.3

    def __post_init__(self):
        self.access_key_id = os.getenv("AWS_ACCESS_KEY_ID", self.access_key_id)
        self.secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY", self.secret_access_key)
        self.session_token = os.getenv("AWS_SESSION_TOKEN", self.session_token)
        self.region = os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", self.region))


@dataclass
class AISConfig:
    api_key: str = ""
    provider: str = "aisstream"
    poll_interval_seconds: int = 300
    request_timeout: int = 30
    max_retries: int = 3
    retry_delay: int = 5
    aishub_url: str = "http://data.aishub.net/ws.php"
    marinetraffic_url: str = "https://services.marinetraffic.com/api/exportvessels/v:8"
    aisstream_url: str = "wss://stream.aisstream.io/v0/stream"

    def __post_init__(self):
        self.api_key = os.getenv("AIS_API_KEY", self.api_key)
        provider = os.getenv("AIS_PROVIDER", self.provider)
        if provider in ("aishub", "marinetraffic", "aisstream"):
            self.provider = provider


@dataclass
class DatabaseConfig:
    db_path: str = ""

    def __post_init__(self):
        if not self.db_path:
            self.db_path = str(DB_DIR / "maritime_intel.db")


@dataclass
class UIConfig:
    window_title: str = "Maritime AI Risk Intelligence Platform"
    window_width: int = 1600
    window_height: int = 900
    dark_theme: bool = True
    map_default_lat: float = 20.0
    map_default_lon: float = 40.0
    map_default_zoom: int = 3


@dataclass
class RiskConfig:
    low_threshold: int = 30
    medium_threshold: int = 70
    danger_zones: list = field(default_factory=lambda: [
        {"name": "Red Sea", "lat_min": 12.0, "lat_max": 30.0, "lon_min": 32.0, "lon_max": 44.0, "weight": 25},
        {"name": "Gulf of Aden", "lat_min": 10.0, "lat_max": 15.0, "lon_min": 43.0, "lon_max": 54.0, "weight": 30},
        {"name": "Strait of Hormuz", "lat_min": 24.0, "lat_max": 27.5, "lon_min": 54.0, "lon_max": 58.0, "weight": 20},
        {"name": "Gulf of Guinea", "lat_min": -5.0, "lat_max": 8.0, "lon_min": -10.0, "lon_max": 12.0, "weight": 28},
        {"name": "South China Sea", "lat_min": 0.0, "lat_max": 23.0, "lon_min": 100.0, "lon_max": 121.0, "weight": 15},
        {"name": "Malacca Strait", "lat_min": -2.0, "lat_max": 8.0, "lon_min": 98.0, "lon_max": 105.0, "weight": 18},
        {"name": "Somalia Coast", "lat_min": -2.0, "lat_max": 12.0, "lon_min": 41.0, "lon_max": 52.0, "weight": 30},
    ])
    speed_anomaly_threshold_knots: float = 2.0
    ais_silence_minutes: int = 60


@dataclass
class AppConfig:
    aws: AWSConfig = field(default_factory=AWSConfig)
    ais: AISConfig = field(default_factory=AISConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    ui: UIConfig = field(default_factory=UIConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)


def load_config() -> AppConfig:
    """Load application configuration from environment and defaults."""
    config = AppConfig()
    config_file = BASE_DIR / "config" / "config.json"
    if config_file.exists():
        try:
            with open(config_file, "r") as f:
                overrides = json.load(f)
            if "poll_interval" in overrides:
                config.ais.poll_interval_seconds = overrides["poll_interval"]
            if "bedrock_model" in overrides:
                config.aws.bedrock_model_id = overrides["bedrock_model"]
            logger.info("Loaded config overrides from config.json")
        except Exception as e:
            logger.warning(f"Failed to load config.json: {e}")
    return config
