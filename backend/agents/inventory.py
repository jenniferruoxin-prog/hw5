"""Inventory agent: stock by SKU and size, shortfalls, which vendor can restock and when, vendor shipping blocks."""

from pydantic_ai.mcp import MCPToolset
from pydantic_ai.models import Model

from agents.base import build_agent
from models import InventoryReport

NAME = "inventory"


def create(model: Model, toolset: MCPToolset):
    # Prompt: prompts/shared_rules.md + prompts/inventory.md. Output: InventoryReport.
    return build_agent(NAME, InventoryReport, model, toolset)
