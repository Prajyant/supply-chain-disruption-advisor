"""Chat service for AI-powered advisory responses.

Enhanced with global context awareness and Bedrock LLM — the chat advisor has access to:
- All active risks (reactive + predictive)
- All tracked shipments and their statuses
- Current weather intelligence
- Network/graph state
- Trade policy events
- Amazon Bedrock (Claude) for intelligent reasoning

This allows it to answer any question about the supply chain state.
"""
import json
import logging
from typing import Any, Optional

from app.retrieval.index import RetrievalIndex

logger = logging.getLogger(__name__)


class ChatService:
    """Service for AI-powered chat advisory with global context and Bedrock LLM."""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.vector_index = None
            cls._instance._global_context: dict[str, Any] = {}
            cls._instance._bedrock_client = None
            cls._instance._bedrock_model_id = None
        return cls._instance

    def __init__(self) -> None:
        if self._bedrock_client is None:
            self._init_bedrock()

    def _init_bedrock(self) -> None:
        """Initialize Bedrock client for chat reasoning."""
        try:
            import boto3
            from app.core.config import get_settings
            settings = get_settings()
            self._bedrock_model_id = settings.bedrock_model_id
            self._bedrock_client = boto3.client(
                "bedrock-runtime",
                region_name=settings.aws_region,
                aws_access_key_id=settings.aws_access_key_id or None,
                aws_secret_access_key=settings.aws_secret_access_key or None,
                aws_session_token=settings.aws_session_token or None,
            )
            logger.info("Chat Bedrock client initialized: model=%s", self._bedrock_model_id)
        except Exception as exc:
            logger.warning("Chat Bedrock initialization failed (will use heuristics): %s", exc)
            self._bedrock_client = None

    def set_index(self, index: RetrievalIndex) -> None:
        """Set the vector index for retrieval."""
        self.vector_index = index

    def update_global_context(
        self,
        *,
        risks: list[dict] | None = None,
        shipments: list[dict] | None = None,
        weather_events: list[dict] | None = None,
        trade_events: list[dict] | None = None,
        network_summary: dict | None = None,
        vessel_fleet_status: dict | None = None,
        vessel_statuses: list[dict] | None = None,
    ) -> None:
        """Update the global context cache used to enrich chat answers.

        Called by the background worker after each ingestion cycle so the
        chat advisor always has fresh system-wide awareness.
        """
        if risks is not None:
            self._global_context["risks"] = risks
        if shipments is not None:
            self._global_context["shipments"] = shipments
        if weather_events is not None:
            self._global_context["weather_events"] = weather_events
        if trade_events is not None:
            self._global_context["trade_events"] = trade_events
        if network_summary is not None:
            self._global_context["network_summary"] = network_summary
        if vessel_fleet_status is not None:
            self._global_context["vessel_fleet_status"] = vessel_fleet_status
        if vessel_statuses is not None:
            self._global_context["vessel_statuses"] = vessel_statuses

    def get_global_context(self) -> dict[str, Any]:
        """Return the current global context snapshot."""
        return dict(self._global_context)

    def chat(self, question: str, top_k: int = 5) -> dict[str, str | list]:
        """Generate a response using Bedrock LLM with full supply chain context.

        The chat advisor combines:
        1. Vector-retrieved relevant chunks (semantic search)
        2. Global context (risks, shipments, weather, trade, network)
        3. Bedrock Claude for intelligent reasoning over all context

        Falls back to heuristic answers if Bedrock is unavailable.
        """
        # Gather vector-retrieved context
        contexts = []
        if self.vector_index:
            contexts = self.vector_index.query(question, top_k=top_k)

        # Try Bedrock-powered answer first
        if self._bedrock_client:
            bedrock_answer = self._bedrock_answer(question, contexts)
            if bedrock_answer:
                return bedrock_answer

        # Fallback: Try to answer from global context with heuristics
        global_answer = self._answer_from_global_context(question)
        if global_answer:
            return global_answer

        if not contexts and not self._global_context:
            return {
                "answer": "No data available yet. The system is loading — please try again in a moment.",
                "supporting_context": [],
                "recommendations": [],
            }

        if not contexts:
            return {
                "answer": "I couldn't find relevant information in the data. Try asking about specific suppliers, disruptions, or risk types.",
                "supporting_context": [],
                "recommendations": [],
            }

        # Heuristic fallback
        answer = self._heuristic_answer(question, contexts)
        recommendations = self._extract_recommendations(contexts)

        return {
            "answer": answer,
            "supporting_context": [c.text for c in contexts],
            "recommendations": recommendations,
        }

    def _bedrock_answer(self, question: str, contexts: list) -> dict | None:
        """Generate an intelligent answer using Bedrock Claude with full context."""
        try:
            # Build comprehensive context for the LLM
            context_parts = []

            # Add retrieved chunks
            if contexts:
                chunks = [c.text[:300] for c in contexts[:5]]
                context_parts.append("Retrieved data:\n" + "\n".join(f"- {c}" for c in chunks))

            # Add FULL global context
            ctx = self._global_context

            # --- All shipments with full details ---
            if ctx.get("shipments"):
                shipments = ctx["shipments"]
                context_parts.append(f"\n=== ALL SHIPMENTS ({len(shipments)} total) ===")
                for s in shipments:
                    shipment_id = s.get("shipment_id", s.get("id", "?"))
                    supplier = s.get("supplier", "?")
                    material = s.get("material", "?")
                    origin = s.get("origin", "?")
                    destination = s.get("destination", "?")
                    status = s.get("status", "unknown")
                    mode = s.get("transport_mode", "?")
                    eta = s.get("eta_date", s.get("eta", "?"))
                    value = s.get("declared_value_usd", "?")
                    inventory = s.get("inventory_days_cover", "?")
                    priority = s.get("priority", "?")
                    vessel = s.get("vessel_name", "")
                    line = (
                        f"  [{status.upper()}] {shipment_id}: {material} from {supplier} | "
                        f"{origin} → {destination} | mode: {mode} | ETA: {eta} | "
                        f"value: ${value} | inventory cover: {inventory} days | priority: {priority}"
                    )
                    if vessel:
                        line += f" | vessel: {vessel}"
                    context_parts.append(line)

            # --- All risks with full details ---
            if ctx.get("risks"):
                risks = ctx["risks"]
                context_parts.append(f"\n=== ALL ACTIVE RISKS ({len(risks)} total) ===")
                for r in risks[:20]:
                    severity = r.get("severity", "?")
                    headline = r.get("headline", r.get("summary", r.get("text", "")))[:150]
                    dtype = r.get("disruption_type", "")
                    supplier = r.get("supplier", "")
                    line = f"  [{severity.upper()}] {headline}"
                    if dtype:
                        line += f" | type: {dtype}"
                    if supplier:
                        line += f" | supplier: {supplier}"
                    context_parts.append(line)

            # --- All weather events ---
            if ctx.get("weather_events"):
                weather = ctx["weather_events"]
                context_parts.append(f"\n=== WEATHER INTELLIGENCE ({len(weather)} events) ===")
                for e in weather[:10]:
                    meta = e.get("metadata", {})
                    loc = meta.get("location", "?")
                    severity = meta.get("severity", "?")
                    summary = meta.get("summary", e.get("text", "")[:100])
                    wind = meta.get("wind_speed_10m", "")
                    precip = meta.get("precipitation", "")
                    line = f"  [{severity.upper()}] {loc}: {summary}"
                    if wind:
                        line += f" | wind: {wind} km/h"
                    if precip:
                        line += f" | rain: {precip} mm"
                    context_parts.append(line)

            # --- All trade policy events ---
            if ctx.get("trade_events"):
                trade = ctx["trade_events"]
                context_parts.append(f"\n=== TRADE POLICY ({len(trade)} events) ===")
                for e in trade[:10]:
                    meta = e.get("metadata", {})
                    severity = meta.get("severity", "?")
                    title = meta.get("title", e.get("text", "")[:120])
                    context_parts.append(f"  [{severity.upper()}] {title}")

            # --- Network summary ---
            if ctx.get("network_summary"):
                net = ctx["network_summary"]
                context_parts.append(
                    f"\n=== NETWORK STATUS ===\n"
                    f"  Total nodes: {net.get('total_nodes', 0)} | At risk: {net.get('at_risk_nodes', 0)}"
                )

            # --- Vessel fleet status (integration point: vessel tracking → chat) ---
            if ctx.get("vessel_fleet_status"):
                fleet = ctx["vessel_fleet_status"]
                context_parts.append(
                    f"\n=== VESSEL FLEET STATUS ===\n"
                    f"  Total tracked: {fleet.get('total', 0)} | Active: {fleet.get('active', 0)} | "
                    f"Stale: {fleet.get('stale', 0)} | AIS Silent: {fleet.get('silent', 0)} | "
                    f"In danger zones: {fleet.get('in_danger_zone', 0)}"
                )
            if ctx.get("vessel_statuses"):
                vessels = ctx["vessel_statuses"]
                context_parts.append(f"\n=== TRACKED VESSELS ({len(vessels)}) ===")
                for v in vessels[:15]:
                    name = v.get("name", v.get("imo_number", "?"))
                    status = v.get("status", "unknown")
                    speed = v.get("speed", 0)
                    dest = v.get("destination", "?")
                    danger = v.get("in_danger_zone", "")
                    supplier = v.get("linked_supplier", "")
                    line = f"  [{status.upper()}] {name}: {speed:.1f}kts → {dest}"
                    if danger:
                        line += f" | ⚠ DANGER: {danger}"
                    if supplier:
                        line += f" | supplier: {supplier}"
                    context_parts.append(line)

            context_text = "\n".join(context_parts) if context_parts else "No context data available yet."

            prompt = (
                "You are a supply chain disruption advisor with FULL visibility into the system.\n"
                "You have access to ALL shipments, risks, weather, trade events, and network state.\n"
                "Answer the user's question using the complete context below.\n"
                "Be specific — use shipment IDs, supplier names, routes, values, and dates.\n"
                "Use bullet points for lists. If recommending actions, tag each with an owner: "
                "[Supplier], [Carrier], [Procurement], [Plant], [Inventory], [Compliance].\n\n"
                f"FULL SUPPLY CHAIN CONTEXT:\n{context_text}\n\n"
                f"USER QUESTION: {question}\n\n"
                "Respond with a JSON object: {\"answer\": \"...\", \"recommendations\": [\"action1\", \"action2\", ...]}"
            )

            response = self._bedrock_client.converse(
                modelId=self._bedrock_model_id,
                messages=[{"role": "user", "content": [{"text": prompt}]}],
                inferenceConfig={"maxTokens": 1500, "temperature": 0.2},
            )

            output = response["output"]["message"]["content"][0]["text"]

            # Try to parse as JSON
            try:
                clean = output.strip()
                if clean.startswith("```"):
                    clean = clean.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
                parsed = json.loads(clean)
                return {
                    "answer": parsed.get("answer", output),
                    "supporting_context": [c.text for c in contexts[:3]] if contexts else [],
                    "recommendations": parsed.get("recommendations", [])[:5],
                }
            except (json.JSONDecodeError, KeyError):
                return {
                    "answer": output,
                    "supporting_context": [c.text for c in contexts[:3]] if contexts else [],
                    "recommendations": [],
                }

        except Exception as exc:
            logger.warning("Bedrock chat failed (falling back to heuristics): %s", exc)
            return None

    def _answer_from_global_context(self, question: str) -> dict | None:
        """Try to answer system-wide questions from global context.

        Handles questions about:
        - Overall risk status / counts
        - Shipment statuses / delays
        - Weather conditions at logistics nodes
        - Trade policy impacts
        - Network health
        """
        q = question.lower()
        ctx = self._global_context

        # --- Shipment questions ---
        shipments = ctx.get("shipments", [])
        if shipments and any(kw in q for kw in ["shipment", "shipping", "delivery", "delayed", "in transit", "how many"]):
            return self._summarize_shipments(q, shipments)

        # --- Risk overview questions ---
        risks = ctx.get("risks", [])
        if risks and any(kw in q for kw in ["risk", "critical", "disruption", "alert", "threat", "danger"]):
            return self._summarize_risks(q, risks)

        # --- Weather questions ---
        weather = ctx.get("weather_events", [])
        if weather and any(kw in q for kw in ["weather", "storm", "rain", "wind", "temperature", "climate"]):
            return self._summarize_weather(q, weather)

        # --- Trade policy questions ---
        trade = ctx.get("trade_events", [])
        if trade and any(kw in q for kw in ["trade", "tariff", "sanction", "embargo", "policy", "customs"]):
            return self._summarize_trade(q, trade)

        # --- Network / supply chain overview ---
        network = ctx.get("network_summary", {})
        if network and any(kw in q for kw in ["network", "supply chain", "overview", "status", "health", "summary"]):
            return self._summarize_network(q, network, risks, shipments)

        # --- Vessel tracking questions ---
        # Integration point: vessel fleet status feeds into chat advisor
        vessel_statuses = ctx.get("vessel_statuses", [])
        vessel_fleet = ctx.get("vessel_fleet_status", {})
        if (vessel_statuses or vessel_fleet) and any(
            kw in q for kw in ["vessel", "ship", "fleet", "imo", "ais", "maritime", "tracking", "route", "danger zone"]
        ):
            return self._summarize_vessels(q, vessel_statuses, vessel_fleet)

        return None

    def _summarize_shipments(self, q: str, shipments: list[dict]) -> dict:
        """Summarize shipment data for the user."""
        total = len(shipments)
        by_status: dict[str, int] = {}
        for s in shipments:
            status = s.get("status", "unknown")
            by_status[status] = by_status.get(status, 0) + 1

        delayed = by_status.get("delayed", 0)
        in_transit = by_status.get("in_transit", 0)
        delivered = by_status.get("delivered", 0)
        rerouted = by_status.get("rerouted", 0)
        cancelled = by_status.get("cancelled", 0)

        parts = [f"There are **{total} tracked shipments** in the system."]
        if in_transit:
            parts.append(f"• {in_transit} in transit")
        if delayed:
            parts.append(f"• {delayed} delayed ⚠️")
        if rerouted:
            parts.append(f"• {rerouted} rerouted")
        if delivered:
            parts.append(f"• {delivered} delivered ✓")
        if cancelled:
            parts.append(f"• {cancelled} cancelled")

        # If asking about specific delayed shipments, list them
        recommendations = []
        if "delay" in q or "late" in q:
            delayed_shipments = [s for s in shipments if s.get("status") == "delayed"]
            if delayed_shipments:
                for s in delayed_shipments[:5]:
                    parts.append(
                        f"  → {s.get('supplier', 'Unknown')} ({s.get('material', '')}): "
                        f"{s.get('origin', '')} → {s.get('destination', '')}"
                    )
                recommendations = [
                    "Increase safety stock for materials from delayed suppliers.",
                    "Contact delayed suppliers for updated ETAs.",
                    "Evaluate alternate sourcing for critical delayed materials.",
                ]

        return {
            "answer": "\n".join(parts),
            "supporting_context": [f"Shipment status breakdown: {by_status}"],
            "recommendations": recommendations,
        }

    def _summarize_risks(self, q: str, risks: list[dict]) -> dict:
        """Summarize risk data for the user."""
        total = len(risks)
        by_severity: dict[str, int] = {}
        by_type: dict[str, int] = {}
        for r in risks:
            sev = r.get("severity", "low")
            by_severity[sev] = by_severity.get(sev, 0) + 1
            dtype = r.get("disruption_type", "unknown")
            by_type[dtype] = by_type.get(dtype, 0) + 1

        critical = by_severity.get("critical", 0)
        high = by_severity.get("high", 0)

        parts = [f"Currently tracking **{total} active risks**."]
        if critical:
            parts.append(f"• 🔴 {critical} critical")
        if high:
            parts.append(f"• 🟠 {high} high")
        if by_severity.get("medium"):
            parts.append(f"• 🟡 {by_severity['medium']} medium")

        if by_type:
            parts.append(f"\nDisruption types: {', '.join(f'{k} ({v})' for k, v in sorted(by_type.items(), key=lambda x: -x[1]))}")

        # Show top critical risks
        recommendations = []
        critical_risks = [r for r in risks if r.get("severity") == "critical"]
        if critical_risks:
            parts.append("\n**Critical risks:**")
            for r in critical_risks[:3]:
                headline = r.get("headline", r.get("summary", ""))[:80]
                parts.append(f"  → {headline}")
            recommendations = critical_risks[0].get("recommendations", [])[:3]

        if not recommendations:
            high_risks = [r for r in risks if r.get("severity") == "high"]
            if high_risks:
                recommendations = high_risks[0].get("recommendations", [])[:3]

        return {
            "answer": "\n".join(parts),
            "supporting_context": [f"Risk severity breakdown: {by_severity}"],
            "recommendations": recommendations,
        }

    def _summarize_weather(self, q: str, weather_events: list[dict]) -> dict:
        """Summarize weather intelligence."""
        if not weather_events:
            return {
                "answer": "No notable weather conditions affecting logistics nodes at this time.",
                "supporting_context": [],
                "recommendations": [],
            }

        parts = [f"**{len(weather_events)} weather events** affecting logistics nodes:"]
        for event in weather_events[:7]:
            meta = event.get("metadata", {})
            loc = meta.get("location", "Unknown")
            sev = meta.get("severity", "low")
            desc = meta.get("summary", event.get("text", "")[:80])
            icon = {"critical": "🔴", "high": "🟠", "medium": "🟡"}.get(sev, "⚪")
            parts.append(f"  {icon} **{loc}**: {desc[:100]}")

        recommendations = []
        severe = [e for e in weather_events if e.get("metadata", {}).get("severity") in ("critical", "high")]
        if severe:
            recommendations = [
                "Monitor affected port/airport operations for delays.",
                "Pre-position inventory at alternate distribution points.",
                "Alert carriers operating in affected regions.",
            ]

        return {
            "answer": "\n".join(parts),
            "supporting_context": [e.get("text", "")[:200] for e in weather_events[:3]],
            "recommendations": recommendations,
        }

    def _summarize_trade(self, q: str, trade_events: list[dict]) -> dict:
        """Summarize trade policy intelligence."""
        if not trade_events:
            return {
                "answer": "No active trade policy events affecting your supply chain.",
                "supporting_context": [],
                "recommendations": [],
            }

        parts = [f"**{len(trade_events)} trade policy events** detected:"]
        for event in trade_events[:7]:
            meta = event.get("metadata", {})
            sev = meta.get("severity", "low")
            text = event.get("text", "")[:120]
            icon = {"critical": "🔴", "high": "🟠", "medium": "🟡"}.get(sev, "⚪")
            parts.append(f"  {icon} {text}")

        recommendations = [
            "Review affected trade lanes for compliance requirements.",
            "Assess tariff impact on landed cost for affected SKUs.",
            "Evaluate alternate sourcing from unaffected regions.",
        ]

        return {
            "answer": "\n".join(parts),
            "supporting_context": [e.get("text", "")[:200] for e in trade_events[:3]],
            "recommendations": recommendations,
        }

    def _summarize_network(self, q: str, network: dict, risks: list, shipments: list) -> dict:
        """Provide a high-level supply chain health summary."""
        total_nodes = network.get("total_nodes", 0)
        at_risk_nodes = network.get("at_risk_nodes", 0)
        total_risks = len(risks) if risks else 0
        total_shipments = len(shipments) if shipments else 0
        critical_risks = sum(1 for r in (risks or []) if r.get("severity") == "critical")
        delayed_shipments = sum(1 for s in (shipments or []) if s.get("status") == "delayed")

        health = "healthy"
        if critical_risks > 0:
            health = "at risk"
        elif at_risk_nodes > total_nodes * 0.3:
            health = "under stress"

        parts = [
            f"**Supply Chain Health: {health.upper()}**",
            f"• Network: {total_nodes} nodes ({at_risk_nodes} at risk)",
            f"• Active risks: {total_risks} ({critical_risks} critical)",
            f"• Shipments: {total_shipments} tracked ({delayed_shipments} delayed)",
        ]

        recommendations = []
        if critical_risks > 0:
            recommendations.append("Address critical risks immediately — see risk dashboard for details.")
        if delayed_shipments > 0:
            recommendations.append(f"{delayed_shipments} shipments delayed — review for expediting options.")
        if at_risk_nodes > 0:
            recommendations.append("Run risk propagation to assess downstream impact on at-risk nodes.")

        return {
            "answer": "\n".join(parts),
            "supporting_context": [],
            "recommendations": recommendations,
        }

    def _summarize_vessels(self, q: str, vessel_statuses: list[dict], fleet_status: dict) -> dict:
        """Summarize vessel tracking data for the user.

        Integration point: allows users to ask about vessel positions,
        fleet status, danger zones, and specific vessels by name.
        """
        parts = []
        recommendations = []

        # Fleet overview
        if fleet_status:
            total = fleet_status.get("total", 0)
            active = fleet_status.get("active", 0)
            stale = fleet_status.get("stale", 0)
            silent = fleet_status.get("silent", 0)
            in_danger = fleet_status.get("in_danger_zone", 0)

            parts.append(f"**Fleet Status: {total} vessels tracked**")
            parts.append(f"• 🟢 {active} active")
            if stale:
                parts.append(f"• 🟡 {stale} stale (no update > 1 hour)")
            if silent:
                parts.append(f"• 🔴 {silent} AIS silent (no signal > 6 hours)")
            if in_danger:
                parts.append(f"• ⚠️ {in_danger} in danger zones")

        # Specific vessel query
        q_lower = q.lower()
        if vessel_statuses:
            # Check if asking about a specific vessel
            for v in vessel_statuses:
                name = (v.get("name") or "").lower()
                imo = v.get("imo_number", "")
                if name and name in q_lower or imo in q_lower:
                    parts.append(f"\n**{v.get('name', imo)}** (IMO: {imo})")
                    parts.append(f"  Position: {v.get('latitude', 0):.4f}N, {v.get('longitude', 0):.4f}E")
                    parts.append(f"  Speed: {v.get('speed', 0):.1f} kts | Course: {v.get('course', 0):.0f}°")
                    parts.append(f"  Destination: {v.get('destination', 'Not declared')}")
                    parts.append(f"  Status: {v.get('status', 'unknown')}")
                    if v.get("in_danger_zone"):
                        parts.append(f"  ⚠️ In danger zone: {v['in_danger_zone']}")
                    if v.get("linked_supplier"):
                        parts.append(f"  Linked to: {v['linked_supplier']}")
                    break

            # Danger zone query
            if any(kw in q_lower for kw in ["danger", "red sea", "gulf", "hormuz", "piracy"]):
                danger_vessels = [v for v in vessel_statuses if v.get("in_danger_zone")]
                if danger_vessels:
                    parts.append(f"\n**Vessels in danger zones ({len(danger_vessels)}):**")
                    for v in danger_vessels[:5]:
                        parts.append(f"  • {v.get('name', v['imo_number'])} — {v.get('in_danger_zone')}")
                    recommendations.append("Monitor vessels in danger zones closely for AIS gaps or speed changes.")
                    recommendations.append("Consider rerouting if risk escalates.")

            # Silent vessels
            if "silent" in q_lower or "ais" in q_lower:
                silent_vessels = [v for v in vessel_statuses if v.get("status") == "silent"]
                if silent_vessels:
                    parts.append(f"\n**AIS Silent vessels ({len(silent_vessels)}):**")
                    for v in silent_vessels[:5]:
                        parts.append(f"  • {v.get('name', v['imo_number'])}")
                    recommendations.append("Investigate AIS-silent vessels — may indicate equipment failure or intentional concealment.")

        if not parts:
            parts.append("Vessel tracking is active. Ask about specific vessels by name, fleet status, or danger zones.")

        return {
            "answer": "\n".join(parts),
            "supporting_context": [f"Fleet: {fleet_status}"] if fleet_status else [],
            "recommendations": recommendations,
        }

    def _heuristic_answer(self, question: str, contexts: list) -> str:
        """Generate a heuristic-based answer.

        Args:
            question: The user's question
            contexts: The retrieved contexts

        Returns:
            Heuristic answer
        """
        question_lower = question.lower()

        # Count sources
        sources = {}
        for ctx in contexts:
            source = ctx.source
            sources[source] = sources.get(source, 0) + 1

        # Build answer based on question type
        if "risk" in question_lower or "disruption" in question_lower:
            total = len(contexts)
            if total > 0:
                return f"Based on the data, I found {total} relevant events related to your question. The main sources are: {', '.join(sources.keys())}."

        if "supplier" in question_lower:
            suppliers = set()
            for ctx in contexts:
                supplier = ctx.metadata.get("supplier", "")
                if supplier:
                    suppliers.add(supplier)
            if suppliers:
                return f"The following suppliers are mentioned in the data: {', '.join(list(suppliers)[:5])}."

        if "mitigation" in question_lower or "recommend" in question_lower:
            recommendations = self._extract_recommendations(contexts)
            if recommendations:
                return f"Based on the detected risks, here are recommended mitigation actions: {'; '.join(recommendations[:3])}."

        # Default answer
        total = len(contexts)
        if total > 0:
            return f"Found {total} relevant events in the data from {len(sources)} source(s)."
        return "I found limited information in the data. Try asking about specific risk types, suppliers, or mitigation strategies."

    def _extract_recommendations(self, contexts: list) -> list[str]:
        """Extract recommendations from contexts.

        Args:
            contexts: The retrieved contexts

        Returns:
            List of recommendation strings
        """
        recommendations = set()

        for ctx in contexts:
            metadata = ctx.metadata
            if "recommendations" in metadata:
                recs = metadata["recommendations"]
                if isinstance(recs, list):
                    recommendations.update(recs)

        return list(recommendations)[:5]
