"""Customer Service agent: drafts customer messages from verified facts. Drafts stay on the board; nothing is sent."""

from pydantic_ai.mcp import MCPToolset
from pydantic_ai.models import Model

from agents.base import build_agent
from models import CustomerServiceReport

NAME = "customer_service"


def create(model: Model, toolset: MCPToolset):
    # Prompt: prompts/shared_rules.md + prompts/customer_service.md. Output: CustomerServiceReport.
    return build_agent(NAME, CustomerServiceReport, model, toolset)
