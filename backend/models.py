"""Data types for the Campus Customs agent team.

- Ticket: one row of the tickets table, handed to the Boss by the backend.
- Report types: what each specialist returns (the agent's structured output).
- BossDecision: the Boss's final call on a ticket.
- TeamDeps: per-ticket state shared by every agent run (delegation chain, logs, limits).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from agents.team import Team

AgentName = Literal["boss", "inventory", "accounting", "facilities", "customer_service"]

# The five action status words from the shared rules.
ActionStatus = Literal["recommended", "awaiting_approval", "executed", "refused", "resolved"]
TicketStatus = Literal["open", "in_progress", "awaiting_approval", "blocked", "resolved"]


# ---------- Ticket input ----------

class Ticket(BaseModel):
    """A row from the tickets table (working copy), exactly as stored."""
    id: int
    type: str
    requester: str
    subject: str
    sku: str | None = None
    size: str | None = None
    qty: int | None = None
    lease_id: int | None = None
    invoice_id: int | None = None
    status: str
    notes: str | None = None
    created_at: str


# ---------- Building blocks shared by every report ----------

class Finding(BaseModel):
    fact: str = Field(description="One verified fact, with exact values as returned.")
    source: str = Field(description="Where it came from: an MCP tool name, 'ticket record', or an agent name.")


class Action(BaseModel):
    description: str = Field(description="What should happen or what happened, with exact amounts and references.")
    owner: AgentName | Literal["human"] = Field(description="Who is responsible for the next step.")
    status: ActionStatus
    evidence_tool: str | None = Field(
        default=None,
        description="Required when status is 'executed': the tool that did it and returned success in this run.",
    )


class AgentReport(BaseModel):
    """Common fields every specialist returns to whoever delegated to it."""
    ticket_id: int
    answer: str = Field(description="Direct answer to the question you were asked, in 1-3 sentences.")
    findings: list[Finding] = Field(default_factory=list)
    recommendation: str | None = None
    actions: list[Action] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list, description="Anything that could not be verified, blocked delegations, missing tools.")


# ---------- Role-specific reports ----------

class StockCheck(BaseModel):
    sku: str
    size: str
    qty_requested: int
    qty_on_hand: int
    shortfall: int = Field(description="max(qty_requested - qty_on_hand, 0)")
    can_fill_from_stock: bool


class VendorOption(BaseModel):
    vendor_id: int
    name: str
    specialty: str
    lead_days: int
    can_ship: bool
    blocking_invoice_ids: list[int] = Field(default_factory=list)
    earliest_arrival: str | None = Field(default=None, description="date_today + lead_days, only if can_ship.")


class InventoryReport(AgentReport):
    stock_checks: list[StockCheck] = Field(default_factory=list)
    vendor_options: list[VendorOption] = Field(default_factory=list)


class PaymentProposal(BaseModel):
    kind: Literal["invoice", "rent", "purchase_order"]
    reference: str = Field(description="e.g. 'invoice 501', 'lease 1', or 'PO CC-HOOD-NAVY M x12'.")
    payee: str
    amount: float
    due_date: str | None = None
    due_status: str | None = Field(default=None, description="overdue / due today / upcoming, with days, vs desk.date_today.")
    cash_before: float | None = Field(default=None, description="Verified balance before payment; null if no tool returned it.")
    projected_balance: float | None = Field(default=None, description="cash_before minus this and other proposed payments; null if unknown.")
    duplicate_checked: bool = False
    status: Literal["awaiting_approval", "refused"] = Field(
        description="Payments are never executed by an agent: awaiting_approval (needs a human) or refused (rule broken, e.g. negative cash).",
    )
    reason: str = Field(description="Why this status, e.g. 'needs human approval' or 'would leave balance at -$X'.")


class MarginCheck(BaseModel):
    sku: str
    qty: int
    unit_cost: float
    list_price: float
    proposed_price: float | None = None
    margin_per_unit_at_list: float
    margin_per_unit_at_proposed: float | None = None
    margin_pct_at_proposed: float | None = None
    below_cost: bool = Field(description="True if proposed_price <= unit_cost.")
    price_floor: float = Field(description="Lowest price that still covers unit_cost.")


class AccountingReport(AgentReport):
    payment_proposals: list[PaymentProposal] = Field(default_factory=list)
    margin_checks: list[MarginCheck] = Field(default_factory=list)


class LeaseStatus(BaseModel):
    lease_id: int
    space_name: str
    landlord: str
    monthly_rent: float
    next_due: str
    days_until_due: int
    rent_status: Literal["upcoming", "due", "overdue"]
    inconsistencies: list[str] = Field(default_factory=list)


class FacilitiesReport(AgentReport):
    lease_status: LeaseStatus | None = None


class CustomerDraft(BaseModel):
    to: str
    subject: str
    body: str = Field(description="The message text, clearly labelled as a draft.")
    status: Literal["draft"] = "draft"


class CustomerServiceReport(AgentReport):
    drafts: list[CustomerDraft] = Field(default_factory=list)


class BossDecision(BaseModel):
    ticket_id: int
    summary: str
    agents_consulted: list[AgentName] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    actions: list[Action] = Field(default_factory=list)
    customer_draft: CustomerDraft | None = None
    ticket_status: TicketStatus
    next_steps: list[str] = Field(default_factory=list, description="What the human needs to do next.")
    limitations: list[str] = Field(default_factory=list)


# ---------- Run records (for the board / audit) ----------

class DelegationRecord(BaseModel):
    from_agent: AgentName
    to_agent: AgentName
    ticket_id: int
    question: str
    depth: int
    outcome: Literal["answered", "refused", "error", "reused"]
    note: str | None = None


class ToolCallRecord(BaseModel):
    agent: AgentName
    tool: str
    args: dict
    ok: bool
    error: str | None = None


class TicketRun(BaseModel):
    """Everything one ticket run produced: the Boss's decision plus the trail behind it."""
    run_id: str
    ticket: Ticket
    date_today: str
    model: str
    decision: BossDecision | None
    error: str | None = None
    delegations: list[DelegationRecord] = Field(default_factory=list)
    tool_calls: list[ToolCallRecord] = Field(default_factory=list)
    requests: int = 0
    input_tokens: int = 0
    output_tokens: int = 0


# ---------- Shared per-ticket state (PydanticAI deps) ----------

@dataclass
class TeamDeps:
    """Passed to every agent run for one ticket. `chain` is who is currently working
    (boss -> ... -> this agent); the lists and cache are shared by the whole ticket."""
    team: "Team"
    run_id: str
    ticket: Ticket
    date_today: str
    chain: list[AgentName]
    delegations: list[DelegationRecord] = field(default_factory=list)
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    answers: dict[tuple[str, str], str] = field(default_factory=dict)

    @property
    def me(self) -> AgentName:
        return self.chain[-1]

    @property
    def depth(self) -> int:
        return len(self.chain) - 1
