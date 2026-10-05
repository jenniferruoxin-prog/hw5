"""Accounting agent: cash, invoices, margins and discounts; prepares payments and purchase orders for human approval."""

from pydantic_ai.mcp import MCPToolset
from pydantic_ai.models import Model

from agents.base import build_agent
from models import AccountingReport

NAME = "accounting"


def create(model: Model, toolset: MCPToolset):
    # Prompt: prompts/shared_rules.md + prompts/accounting.md. Output: AccountingReport.
    return build_agent(NAME, AccountingReport, model, toolset)
