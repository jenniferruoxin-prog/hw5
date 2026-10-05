"""The Campus Customs agent team: five agents, one MCP toolset, one ticket loop.

    team = Team()
    run = await team.run_ticket(101)

The ticket row comes from the MCP server (get_ticket) and is handed to the Boss. The Boss
delegates with delegate_to, and any teammate can delegate to any other (full connectivity),
within the limits in config.py. All shop facts and every database change go through the MCP
server; the human-only approval tools are hidden from the agents and called by
approve_payment()/reject_payment() below on behalf of a named human.
"""

from __future__ import annotations

import json
import shutil
import sys
import uuid
from pathlib import Path

from fastmcp import Client
from fastmcp.client.transports import StdioTransport
from pydantic_ai import Agent, RunContext
from pydantic_ai.exceptions import UsageLimitExceeded
from pydantic_ai.mcp import MCPToolset
from pydantic_ai.usage import RunUsage

import audit
from agents import accounting, boss, customer_service, facilities, inventory
from agents.base import run_agent
from config import DB_PATH, HW5_DIR, MCP_SERVER_SCRIPT, MODEL_NAME, ORIGINAL_DB_PATH, build_model
from models import AgentName, TeamDeps, Ticket, TicketRun, ToolCallRecord

ROLE_MODULES = (boss, inventory, accounting, facilities, customer_service)

# Must match HUMAN_ONLY_TOOLS in mcp_server/server.py. Agents never see these tools.
HUMAN_ONLY_TOOLS = frozenset({"approve_payment", "reject_payment", "record_human_decision"})


def build_mcp_toolset(db_path: Path = DB_PATH) -> MCPToolset:
    """Our FastMCP server (mcp_server/server.py) over stdio, pointed at the working copy.
    Every call an agent makes is logged on the ticket, tagged with the agent that made it."""

    async def log_call(ctx: RunContext[TeamDeps], call_tool, name: str, args: dict):
        record = ToolCallRecord(agent=ctx.deps.me, tool=name, args=args, ok=True)
        ctx.deps.tool_calls.append(record)
        try:
            return await call_tool(name, args)
        except Exception as exc:
            record.ok = False
            record.error = str(exc)[:300]
            raise

    transport = StdioTransport(
        command=sys.executable,
        args=[str(MCP_SERVER_SCRIPT)],
        env={"CAMPUS_DB_PATH": str(db_path)},
        cwd=str(HW5_DIR),
    )
    return MCPToolset(Client(transport), process_tool_call=log_call)


def reset_working_db() -> None:
    """Copy the original database over the working copy (do this before a full run)."""
    shutil.copyfile(ORIGINAL_DB_PATH, DB_PATH)
    audit.append({"event": "database_reset", "from": ORIGINAL_DB_PATH.name, "to": DB_PATH.name})


def new_run_id() -> str:
    return uuid.uuid4().hex[:12]


def _tool_data(result) -> dict:
    """The JSON a FastMCP tool returned."""
    if getattr(result, "data", None) is not None:
        return result.data
    return json.loads(result.content[0].text)


class Team:
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.model = build_model()  # gpt-6-luna via Portkey, shared by all five agents
        self.toolset = build_mcp_toolset(db_path)
        agent_tools = self.toolset.filtered(lambda ctx, tool_def: tool_def.name not in HUMAN_ONLY_TOOLS)
        self.agents: dict[AgentName, Agent] = {m.NAME: m.create(self.model, agent_tools) for m in ROLE_MODULES}

    async def call(self, tool: str, args: dict | None = None) -> dict:
        """Call an MCP tool directly (backend / human side, not an agent)."""
        async with self.toolset:
            return _tool_data(await self.toolset.client.call_tool(tool, args or {}))

    async def load_ticket(self, ticket_id: int) -> tuple[Ticket, str]:
        data = await self.call("get_ticket", {"ticket_id": ticket_id})
        return Ticket(**data["ticket"]), data["date_today"]

    async def run_ticket(self, ticket_id: int, run_id: str | None = None) -> TicketRun:
        run_id = run_id or new_run_id()
        decision, error = None, None
        usage = RunUsage()
        # Keep the MCP server process open for the whole ticket (all nested agent runs share it).
        async with self.toolset:
            ticket, date_today = await self.load_ticket(ticket_id)
            deps = TeamDeps(team=self, run_id=run_id, ticket=ticket, date_today=date_today, chain=["boss"])
            audit.append({"event": "ticket_start", "run_id": run_id, "ticket_id": ticket_id, "model": MODEL_NAME,
                          "date_today": date_today, "ticket": ticket.model_dump()})
            prompt = (
                "New ticket on the board. Work it according to your rules and return your decision.\n\n"
                f"Ticket record (from the MCP get_ticket tool):\n{ticket.model_dump_json(indent=1)}\n\n"
                f"Shop date (desk.date_today): {date_today}"
            )
            try:
                result = await run_agent(self.agents["boss"], prompt, deps, usage)
                decision = result.output
            except UsageLimitExceeded as exc:
                error = f"Loop limit reached for this ticket: {exc}"
            except Exception as exc:
                error = f"{type(exc).__name__}: {str(exc)[:300]}"
            if decision is not None:
                error = await self._sync_status(run_id, ticket_id, decision) or error

        run = TicketRun(
            run_id=run_id, ticket=ticket, date_today=date_today, model=MODEL_NAME, decision=decision, error=error,
            delegations=deps.delegations, tool_calls=deps.tool_calls,
            requests=usage.requests, input_tokens=usage.input_tokens, output_tokens=usage.output_tokens,
        )
        audit.append({"event": "ticket_end", "run_id": run_id, "ticket_id": ticket_id,
                      "ticket_status": decision.ticket_status if decision else None, "error": error,
                      "delegations": len(deps.delegations), "mcp_tool_calls": len(deps.tool_calls),
                      "failed_tool_calls": sum(not c.ok for c in deps.tool_calls),
                      "usage": {"requests": usage.requests, "tool_calls": usage.tool_calls,
                                "input_tokens": usage.input_tokens, "output_tokens": usage.output_tokens}})
        return run

    async def _sync_status(self, run_id: str, ticket_id: int, decision) -> str | None:
        """Put the Boss's final status on the board (through MCP) if the Boss didn't set it itself.
        The MCP tool still refuses 'resolved' while a payment request is pending."""
        current = (await self.call("get_ticket", {"ticket_id": ticket_id}))["ticket"]["status"]
        wanted = decision.ticket_status
        if wanted == "open" or wanted == current:
            return None
        try:
            out = await self.call("update_ticket_status", {
                "ticket_id": ticket_id, "status": wanted, "author": "boss",
                "note": f"Boss decision: {decision.summary}"[:500],
            })
            audit.append({"event": "status_sync", "run_id": run_id, "ticket_id": ticket_id, "ok": True, "result": out})
            return None
        except Exception as exc:
            audit.append({"event": "status_sync", "run_id": run_id, "ticket_id": ticket_id, "ok": False,
                          "wanted": wanted, "error": str(exc)[:300]})
            return f"Board status not changed to {wanted}: {str(exc)[:200]}"

    # ---------- Human decisions (dashboard) ----------

    async def approve_payment(self, request_id: int, approver: str) -> dict:
        try:
            out = await self.call("approve_payment", {"request_id": request_id, "approver": approver})
        except Exception as exc:
            audit.append({"event": "human_approval", "request_id": request_id, "approver": approver,
                          "ok": False, "error": str(exc)[:300]})
            raise
        audit.append({"event": "human_approval", "ticket_id": out.get("ticket_id"), "request_id": request_id,
                      "approver": approver, "ok": True, "result": out})
        return out

    async def record_decision(self, ticket_id: int, decided_by: str, decision: str) -> dict:
        out = await self.call("record_human_decision", {"ticket_id": ticket_id, "decided_by": decided_by, "decision": decision})
        audit.append({"event": "human_decision", "ticket_id": ticket_id, "approver": decided_by, "result": out})
        return out

    async def reject_payment(self, request_id: int, approver: str, reason: str) -> dict:
        out = await self.call("reject_payment", {"request_id": request_id, "approver": approver, "reason": reason})
        audit.append({"event": "human_rejection", "ticket_id": out.get("ticket_id"), "request_id": request_id,
                      "approver": approver, "result": out})
        return out
