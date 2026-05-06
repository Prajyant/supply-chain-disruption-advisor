"""AIS (Automatic Identification System) vessel tracking providers.

Extracted and adapted from maritime_ai_platform/ais/ for async FastAPI integration.
Provides IMO-based vessel tracking with multiple provider backends.
"""

from app.ingestion.ais.provider_base import AISProviderBase
from app.ingestion.ais.ais_engine import AISEngine

__all__ = ["AISProviderBase", "AISEngine"]
