"""Campus Customs Multi-Agent Operations — FastAPI backend for the dashboard.

Run from backend/:   uvicorn main:app --reload --port 8000

Every shop fact and every database change goes through the MCP server (via Team.call),
so this file never opens the database. Payments: agents only create pending approval
requests; POST /api/approvals/{id}/approve (a human click) is the only thing that pays.
"""

from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import audit
from agents.team import Team, new_run_id, reset_working_db
from config import MODEL_NAME

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("campus_customs.api")

team: Team | None = None
runs: dict[str, dict] = {}          # run_id -> status of a ticket run started from the dashboard
_run_tasks: set[asyncio.Task] = set()


@asynccontextmanager
async def lifespan(_: FastAPI):
    global team
    team = Team()
    # Keep one MCP server process open for the app's lifetime (all routes and runs share it).
    async with team.toolset:
        yield


app = FastAPI(title="Campus Customs Ops API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


def _team() -> Team:
    if team is None:
        raise HTTPException(503, "Agent team is not ready.")
    return team


async def _mcp(tool: str, args: dict | None = None) -> dict:
    """Call an MCP tool; tool refusals (ToolError) come back as 400 with the tool's message."""
    try:
        return await _team().call(tool, args)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc


def _running() -> list[dict]:
    return [r for r in runs.values() if r["status"] == "running"]


# ---------- Health ----------

@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok", "model": MODEL_NAME, "runs_in_progress": len(_running())}


# ---------- Tickets ----------

@app.get("/api/tickets")
async def list_tickets() -> dict:
    data = await _mcp("list_tickets")
    for t in data["tickets"]:
        t["board_state"] = "resolved" if t["is_resolved"] else "open"
        t["running"] = any(r["ticket_id"] == t["id"] for r in _running())
    return data


@app.get("/api/tickets/{ticket_id}")
async def get_ticket(ticket_id: int) -> dict:
    return await _mcp("get_ticket", {"ticket_id": ticket_id})


async def _run_in_background(run_id: str, ticket_id: int) -> None:
    try:
        result = await _team().run_ticket(ticket_id, run_id=run_id)
        runs[run_id].update(status="error" if result.error else "done", error=result.error,
                            result=result.model_dump(mode="json"))
    except Exception as exc:  # e.g. the ticket vanished after a reset
        log.exception("Run %s failed", run_id)
        runs[run_id].update(status="error", error=f"{type(exc).__name__}: {exc}")
    finally:
        runs[run_id]["finished_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")


@app.post("/api/tickets/{ticket_id}/run", status_code=202)
async def run_ticket(ticket_id: int) -> dict:
    """Start the agent team on one ticket. Returns at once; watch /api/events and /api/runs/{run_id}.
    Only one run at a time, so a double click can't burn tokens twice."""
    await _mcp("get_ticket", {"ticket_id": ticket_id})  # 400 if it doesn't exist
    if busy := _running():
        raise HTTPException(409, f"Ticket {busy[0]['ticket_id']} is already running (run {busy[0]['run_id']}).")
    run_id = new_run_id()
    runs[run_id] = {"run_id": run_id, "ticket_id": ticket_id, "status": "running", "model": MODEL_NAME,
                    "started_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "finished_at": None, "error": None, "result": None}
    task = asyncio.create_task(_run_in_background(run_id, ticket_id))
    _run_tasks.add(task)
    task.add_done_callback(_run_tasks.discard)
    return {k: v for k, v in runs[run_id].items() if k != "result"}


@app.get("/api/runs")
async def list_runs() -> list[dict]:
    return [{k: v for k, v in r.items() if k != "result"} for r in runs.values()]


@app.get("/api/runs/{run_id}")
async def get_run(run_id: str) -> dict:
    if run_id not in runs:
        raise HTTPException(404, f"No run {run_id} in this server session.")
    return runs[run_id]


# ---------- Agent events (audit trail) ----------

def _event_view(i: int, r: dict) -> dict:
    """Compact view for the board: what the agent said and which tools it used."""
    view = {k: r.get(k) for k in ("time", "event", "run_id", "ticket_id", "agent", "chain", "depth", "step")}
    view["index"] = i
    ev = r.get("event")
    if ev == "model_response":
        parts = r.get("parts", [])
        view["said"] = "\n".join(p["content"] for p in parts if p.get("type") == "text") or None
        calls = []
        for p in parts:
            if p.get("type") != "tool_call":
                continue
            args = p.get("args")
            try:
                args = json.loads(args) if isinstance(args, str) else args
            except ValueError:
                pass
            calls.append({"tool": p["tool"], "args": args})
        view["tool_calls"] = calls
        view["tokens"] = r.get("usage")
    elif ev == "model_request":
        view["tool_results"] = [{"tool": p.get("tool"), "result": p.get("content")}
                                for p in r.get("parts", []) if p.get("type") in ("tool_result", "retry")]
    elif ev in ("agent_end", "agent_error"):
        view["output"] = r.get("output")
        view["error"] = r.get("error")
    elif ev == "delegation":
        view.update({k: r.get(k) for k in ("from_agent", "to_agent", "question", "outcome", "note")})
    else:
        view["details"] = {k: v for k, v in r.items() if k not in view}
    return view


@app.get("/api/events")
async def events(
    since: int = Query(0, ge=0, description="Return events with index >= since (use next_since to refresh)."),
    ticket_id: int | None = None,
    run_id: str | None = None,
    limit: int = Query(200, ge=1, le=1000),
    since_reset: bool = Query(False, description="Only events after the most recent database reset."),
) -> dict:
    records = audit.read_all()
    start = since
    if since_reset:
        resets = [i for i, r in enumerate(records) if r.get("event") == "database_reset"]
        if resets:
            start = max(start, resets[-1])
    out = []
    for i in range(start, len(records)):
        r = records[i]
        if ticket_id is not None and r.get("ticket_id") != ticket_id:
            continue
        if run_id is not None and r.get("run_id") != run_id:
            continue
        out.append(_event_view(i, r))
    return {"total": len(records), "next_since": len(records), "events": out[-limit:]}


# ---------- Approvals (human only) ----------

class Approval(BaseModel):
    approver: str = Field(min_length=2, description="Full name of the human approving.")


class Rejection(Approval):
    reason: str = Field(min_length=2)


@app.get("/api/approvals")
async def approvals(status: Literal["pending", "approved", "rejected"] | None = None,
                    ticket_id: int | None = None) -> dict:
    args = {k: v for k, v in {"status": status, "ticket_id": ticket_id}.items() if v is not None}
    return await _mcp("list_approval_requests", args)


@app.post("/api/approvals/{request_id}/approve")
async def approve(request_id: int, body: Approval) -> dict:
    """A human clicked Approve: this is the only route that moves cash (invoice, rent or purchase order)."""
    try:
        return await _team().approve_payment(request_id, body.approver)
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post("/api/approvals/{request_id}/reject")
async def reject(request_id: int, body: Rejection) -> dict:
    try:
        return await _team().reject_payment(request_id, body.approver, body.reason)
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc


class Decision(BaseModel):
    decided_by: str = Field(min_length=2, description="Full name of the human deciding.")
    decision: str = Field(min_length=2)


@app.post("/api/tickets/{ticket_id}/decision")
async def human_decision(ticket_id: int, body: Decision) -> dict:
    """A manager puts a decision on the ticket's board (e.g. an authorized discount). Agents read it on the next run."""
    try:
        return await _team().record_decision(ticket_id, body.decided_by, body.decision)
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc


# ---------- Cash ----------

@app.get("/api/cash")
async def cash() -> dict:
    return await _mcp("get_cash_balance", {"account": "checking"})


# ---------- Reset ----------

@app.post("/api/reset")
async def reset() -> dict:
    """Copy the original campus_customs.db over the working copy (fresh run). The audit trail is kept."""
    if busy := _running():
        raise HTTPException(409, f"Can't reset while ticket {busy[0]['ticket_id']} is running.")
    reset_working_db()
    data = await _mcp("list_tickets")
    balance = await _mcp("get_cash_balance", {"account": "checking"})
    return {"status": "reset", "tickets": [{"id": t["id"], "status": t["status"]} for t in data["tickets"]],
            "checking_balance": balance["balance"]}
