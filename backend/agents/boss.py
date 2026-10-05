"""Boss agent: reads each ticket, delegates to the right teammates, combines verified findings and makes the final call."""

from pydantic_ai.mcp import MCPToolset
from pydantic_ai.models import Model

from agents.base import build_agent
from models import BossDecision

NAME = "boss"


def create(model: Model, toolset: MCPToolset):
    # Prompt: prompts/shared_rules.md + prompts/boss.md. Output: BossDecision.
    return build_agent(NAME, BossDecision, model, toolset)
