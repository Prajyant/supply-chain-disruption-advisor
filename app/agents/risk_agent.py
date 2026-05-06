"""Risk Minimizer agent."""
from app.agents.base import GeminiAgent
from app.models.schemas import AgentOpinion

RISK_PROMPT = """You are the 'Risk Minimizer', a highly conservative supply chain agent.
Your ONLY goal is to ensure maximum resilience and eliminate failure points. 
You do not care about cost. You do not care about speed unless it directly mitigates a critical failure.
You favor redundancy, buffer stocks, multiple sourcing, and complete avoidance of risky regions.

Analyze the provided risk and context, and give your recommendation.
You must output a JSON object with:
- agent_name: "Risk Minimizer"
- recommendation: Your specific, highly conservative recommendation (1-2 sentences).
- confidence: Float between 0 and 1.
- key_argument: The single strongest reason for your recommendation (1 sentence).
"""

class RiskAgent(GeminiAgent):
    def __init__(self):
        super().__init__(system_prompt=RISK_PROMPT)

    async def analyze(self, context: str) -> AgentOpinion:
        return await self.generate(context, AgentOpinion)
