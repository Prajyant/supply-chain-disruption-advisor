"""Digital Twin Agent."""
from typing import Optional
from pydantic import BaseModel, Field

from app.agents.base import BedrockAgent

TWIN_PROMPT = """You are the 'Digital Twin Agent', an autonomous AI monitoring a global supply chain graph.
You will be provided with a summary of the current supply chain network, including nodes, edge volumes, and active shipment statuses.
Your goal is to spot emerging macro patterns, clusters of risk, or structural vulnerabilities that individual risk alerts might miss.

Examples of patterns:
- "3 tier-2 suppliers in the same geographic region are showing delayed shipments."
- "A critical plant is entirely dependent on a single supplier that currently has a high risk score."
- "There is a systemic delay in shipments originating from Asian ports."

If you find a pattern, output it as an alert. If the network looks healthy, output an empty list.

You must output a JSON object containing:
- alerts: A list of objects, each with 'title', 'description', and 'severity' ("medium", "high", "critical").
"""

class TwinAlert(BaseModel):
    title: str
    description: str
    severity: str

class TwinAgentResult(BaseModel):
    alerts: list[TwinAlert] = Field(default_factory=list)

class DigitalTwinAgent(BedrockAgent):
    def __init__(self):
        super().__init__(system_prompt=TWIN_PROMPT)

    async def analyze(self, graph_summary: str) -> TwinAgentResult:
        """Analyze the graph summary for patterns."""
        result = await self.generate(graph_summary, TwinAgentResult)
        return result or TwinAgentResult()
