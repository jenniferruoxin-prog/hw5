"""Facilities agent: leases, rent, landlords and other shop-space obligations."""

from pydantic_ai.mcp import MCPToolset
from pydantic_ai.models import Model

from agents.base import build_agent
from models import FacilitiesReport

NAME = "facilities"


def create(model: Model, toolset: MCPToolset):
    # Prompt: prompts/shared_rules.md + prompts/facilities.md. Output: FacilitiesReport.
    return build_agent(NAME, FacilitiesReport, model, toolset)
