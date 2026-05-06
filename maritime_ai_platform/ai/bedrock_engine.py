"""
AWS Bedrock AI Engine for maritime risk intelligence analysis.
Uses Claude 3.5 Sonnet for vessel risk assessment and maritime intelligence.
"""

import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

from config.settings import AWSConfig

logger = logging.getLogger(__name__)


class BedrockAIEngine:
    """AWS Bedrock-powered maritime intelligence analysis engine."""

    def __init__(self, config: AWSConfig):
        self.config = config
        self.client = None
        self._init_client()

    def _init_client(self):
        """Initialize the Bedrock Runtime client."""
        try:
            session_kwargs = {"region_name": self.config.region}
            if self.config.access_key_id and self.config.secret_access_key:
                session_kwargs["aws_access_key_id"] = self.config.access_key_id
                session_kwargs["aws_secret_access_key"] = self.config.secret_access_key
                if self.config.session_token:
                    session_kwargs["aws_session_token"] = self.config.session_token

            session = boto3.Session(**session_kwargs)
            self.client = session.client("bedrock-runtime")
            logger.info(f"Bedrock client initialized (region: {self.config.region})")
        except NoCredentialsError:
            logger.warning("AWS credentials not configured - AI analysis unavailable")
            self.client = None
        except Exception as e:
            logger.error(f"Failed to initialize Bedrock client: {e}")
            self.client = None

    def is_available(self) -> bool:
        """Check if the Bedrock AI engine is available."""
        return self.client is not None

    def analyze_vessel(self, vessel: Dict[str, Any], danger_zones: list = None) -> Dict[str, Any]:
        """
        Perform comprehensive AI risk analysis on a vessel.
        
        Returns structured analysis with risk scoring, route analysis,
        chokepoint assessment, piracy threats, and recommendations.
        """
        if not self.client:
            return self._generate_fallback_analysis(vessel, danger_zones)

        prompt = self._build_analysis_prompt(vessel, danger_zones)

        try:
            response = self.client.invoke_model(
                modelId=self.config.bedrock_model_id,
                contentType="application/json",
                accept="application/json",
                body=json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": self.config.max_tokens,
                    "temperature": self.config.temperature,
                    "messages": [
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ]
                })
            )

            response_body = json.loads(response["body"].read())
            content = response_body.get("content", [{}])[0].get("text", "")
            tokens_used = response_body.get("usage", {}).get("input_tokens", 0) + \
                          response_body.get("usage", {}).get("output_tokens", 0)

            analysis = self._parse_ai_response(content)
            analysis["tokens_used"] = tokens_used
            analysis["model_used"] = self.config.bedrock_model_id
            analysis["timestamp"] = datetime.utcnow().isoformat()

            logger.info(f"AI analysis complete for {vessel.get('name', 'Unknown')} "
                       f"(MMSI: {vessel.get('mmsi')}) - Risk: {analysis.get('risk_level')}")
            return analysis

        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            logger.error(f"Bedrock API error ({error_code}): {e}")
            return self._generate_fallback_analysis(vessel, danger_zones)
        except Exception as e:
            logger.error(f"AI analysis failed: {e}")
            return self._generate_fallback_analysis(vessel, danger_zones)

    def _build_analysis_prompt(self, vessel: Dict[str, Any], danger_zones: list = None) -> str:
        """Build an optimized, token-efficient prompt for vessel analysis."""
        zone_info = ""
        if danger_zones:
            active_zones = []
            lat = vessel.get("latitude", 0)
            lon = vessel.get("longitude", 0)
            for zone in danger_zones:
                if (zone["lat_min"] <= lat <= zone["lat_max"] and
                        zone["lon_min"] <= lon <= zone["lon_max"]):
                    active_zones.append(zone["name"])
            if active_zones:
                zone_info = f"ACTIVE DANGER ZONES: {', '.join(active_zones)}"

        return f"""You are a maritime intelligence analyst. Analyze this vessel and provide a structured risk assessment.

VESSEL DATA:
- Name: {vessel.get('name', 'Unknown')}
- MMSI: {vessel.get('mmsi', 'N/A')}
- IMO: {vessel.get('imo', 'N/A')}
- Type: {vessel.get('vessel_type', 'Unknown')}
- Flag: {vessel.get('flag', 'Unknown')}
- Position: {vessel.get('latitude', 0):.4f}N, {vessel.get('longitude', 0):.4f}E
- Speed: {vessel.get('speed', 0):.1f} knots
- Course: {vessel.get('course', 0):.1f}°
- Heading: {vessel.get('heading', 0):.1f}°
- Destination: {vessel.get('destination', 'Unknown')}
- ETA: {vessel.get('eta', 'Unknown')}
- Nav Status: {vessel.get('nav_status', 'Unknown')}
- Length: {vessel.get('length', 0)}m
- Draught: {vessel.get('draught', 0):.1f}m
{zone_info}

Respond ONLY with valid JSON in this exact format:
{{
    "risk_score": <integer 0-100>,
    "risk_level": "<LOW|MEDIUM|HIGH>",
    "route_analysis": "<brief route assessment>",
    "chokepoint_analysis": "<chokepoint proximity and transit risk>",
    "piracy_threat": "<piracy/armed robbery threat level and details>",
    "weather_concerns": "<weather and sea state concerns for region>",
    "eta_concerns": "<ETA reliability and delay factors>",
    "recommendations": "<operator recommendations for risk mitigation>",
    "summary": "<one-line intelligence summary>"
}}"""

    def _parse_ai_response(self, content: str) -> Dict[str, Any]:
        """Parse the AI response JSON."""
        try:
            start = content.find("{")
            end = content.rfind("}") + 1
            if start >= 0 and end > start:
                json_str = content[start:end]
                result = json.loads(json_str)
                result["risk_score"] = max(0, min(100, int(result.get("risk_score", 50))))
                score = result["risk_score"]
                if score <= 30:
                    result["risk_level"] = "LOW"
                elif score <= 70:
                    result["risk_level"] = "MEDIUM"
                else:
                    result["risk_level"] = "HIGH"
                return result
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Failed to parse AI response: {e}")

        return {
            "risk_score": 50,
            "risk_level": "MEDIUM",
            "route_analysis": "Analysis parsing failed - manual review recommended",
            "chokepoint_analysis": "Unable to determine",
            "piracy_threat": "Unable to determine",
            "weather_concerns": "Unable to determine",
            "eta_concerns": "Unable to determine",
            "recommendations": "Manual intelligence review recommended",
            "summary": "AI analysis response could not be parsed"
        }

    def _generate_fallback_analysis(self, vessel: Dict[str, Any], danger_zones: list = None) -> Dict[str, Any]:
        """Generate a rule-based fallback analysis when Bedrock is unavailable."""
        risk_score = 20
        factors = []

        lat = vessel.get("latitude", 0)
        lon = vessel.get("longitude", 0)
        speed = vessel.get("speed", 0)
        active_zones = []

        if danger_zones:
            for zone in danger_zones:
                if (zone["lat_min"] <= lat <= zone["lat_max"] and
                        zone["lon_min"] <= lon <= zone["lon_max"]):
                    risk_score += zone["weight"]
                    active_zones.append(zone["name"])
                    factors.append(f"In {zone['name']} danger zone")

        if speed < 2 and vessel.get("nav_status") not in ("At anchor", "Moored"):
            risk_score += 15
            factors.append("Abnormally low speed - possible AIS manipulation")

        if speed > 25:
            risk_score += 10
            factors.append("Unusually high speed")

        if not vessel.get("destination"):
            risk_score += 10
            factors.append("No destination declared")

        risk_score = max(0, min(100, risk_score))
        if risk_score <= 30:
            risk_level = "LOW"
        elif risk_score <= 70:
            risk_level = "MEDIUM"
        else:
            risk_level = "HIGH"

        chokepoint = "Not near major chokepoints"
        if active_zones:
            chokepoint = f"Transiting through: {', '.join(active_zones)}"

        piracy = "Low piracy risk in current area"
        if any(z in active_zones for z in ["Gulf of Aden", "Somalia Coast", "Gulf of Guinea"]):
            piracy = f"ELEVATED piracy risk - vessel in {', '.join(active_zones)}"

        return {
            "risk_score": risk_score,
            "risk_level": risk_level,
            "route_analysis": f"Vessel heading {vessel.get('course', 0):.0f}° at {speed:.1f}kts toward {vessel.get('destination', 'Unknown')}",
            "chokepoint_analysis": chokepoint,
            "piracy_threat": piracy,
            "weather_concerns": "Fallback analysis - weather data not available",
            "eta_concerns": f"ETA: {vessel.get('eta', 'Unknown')} - reliability assessment unavailable",
            "recommendations": "; ".join(factors) if factors else "No immediate concerns identified",
            "summary": f"Risk {risk_level} ({risk_score}/100) - {'; '.join(factors[:2]) if factors else 'Normal operations'}",
            "tokens_used": 0,
            "model_used": "fallback-rule-engine",
            "timestamp": datetime.utcnow().isoformat()
        }
