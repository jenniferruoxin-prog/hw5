"""Shared agent wiring: prompts, the delegate_to tool (full connectivity), and output guards.

Every role file (boss.py, inventory.py, ...) calls build_agent() with its own name and output
type, so all five agents get the same shared rules, MCP tools and delegation tool.
"""

from __future__ import annotations

import json
import logging
from dataclasses import replace

from pydantic_ai import Agent, CallToolsNode, ModelRequestNode, ModelRetry, RunContext
from pydantic_ai.exceptions import UsageLimitExceeded
from pydantic_ai.models import Model
from pydantic_ai.toolsets import AbstractToolset
from pydantic_ai.usage import RunUsage

import audit

from config import (
    AGENT_RETRIES,
    MODEL_NAME,
    MAX_DELEGATION_DEPTH,
    MAX_DELEGATIONS_PER_TICKET,
    PROMPTS_DIR,
    TICKET_LIMITS,
)
from models import (
    AccountingReport,
    AgentName,
    BossDecision,
    CustomerDraft,
    CustomerServiceReport,
    DelegationRecord,
    TeamDeps,
)

log = logging.getLogger("campus_customs.agents")


# One line per role, shown to every agent so it knows whom to ask.
ROSTER: dict[AgentName, str] = {
    "boss": "Boss: reads tickets, routes work, combines findings, makes the final call and sets ticket status.",
    "inventory": "Inventory: stock by SKU and size, shortfalls, which vendor can restock, lead times, vendor shipping blocks.",
    "accounting": "Accounting: cash, invoices, margins, discounts, payments and purchase orders prepared for human approval.",
    "facilities": "Facilities: leases, rent, landlords and shop-space obligations.",
    "customer_service": "Customer Service: drafts messages to customers and requesters (drafts only, never sent).",
}


def _normalize(question: str) -> str:
    return " ".join(question.lower().split())


def _record_delegation(d: TeamDeps, rec: DelegationRecord) -> None:
    d.delegations.append(rec)
    audit.append({"event": "delegation", "run_id": d.run_id, "ticket_id": d.ticket.id, **rec.model_dump()})


async def run_agent(agent: Agent, prompt: str, deps: TeamDeps, usage: RunUsage):
    """One agent loop, step by step. Each step is appended to output/audit_trail.json
    as it happens: the request going to the model (prompt / tool results / retries),
    and the model's response (text / tool calls / final-output call / tokens)."""
    base = {"run_id": deps.run_id, "ticket_id": deps.ticket.id, "agent": deps.me,
            "chain": list(deps.chain), "depth": deps.depth}
    audit.append({"event": "agent_start", **base, "model": MODEL_NAME, "prompt": audit._clip(prompt)})
    step = 0
    try:
        async with agent.iter(prompt, deps=deps, usage=usage, usage_limits=TICKET_LIMITS) as run:
            async for node in run:
                if isinstance(node, ModelRequestNode):
                    step += 1
                    audit.append({"event": "model_request", **base, "step": step, **audit.describe_request(node.request)})
                elif isinstance(node, CallToolsNode):
                    audit.append({"event": "model_response", **base, "step": step,
                                  **audit.describe_response(node.model_response)})
            result = run.result
    except Exception as exc:
        audit.append({"event": "agent_error", **base, "steps": step,
                      "error": f"{type(exc).__name__}: {str(exc)[:500]}"})
        raise
    audit.append({"event": "agent_end", **base, "steps": step,
                  "output_type": type(result.output).__name__,
                  "output": result.output.model_dump(mode="json"),
                  "ticket_usage_so_far": {"requests": usage.requests, "tool_calls": usage.tool_calls,
                                          "input_tokens": usage.input_tokens, "output_tokens": usage.output_tokens}})
    return result


def build_agent(name: AgentName, output_type: type, model: Model, toolset: AbstractToolset) -> Agent[TeamDeps, object]:
    agent: Agent[TeamDeps, object] = Agent(
        model,
        name=name,
        deps_type=TeamDeps,
        output_type=output_type,
        toolsets=[toolset],
        retries=AGENT_RETRIES,
    )

    @agent.instructions
    def prompts() -> str:
        # Read on every run, so prompt edits apply without restarting anything.
        shared = (PROMPTS_DIR / "shared_rules.md").read_text(encoding="utf-8")
        role = (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")
        return f"{shared}\n\n{role}"

    @agent.instructions
    def situation(ctx: RunContext[TeamDeps]) -> str:
        d = ctx.deps
        others = "\n".join(f"- `{n}`: {line}" for n, line in ROSTER.items() if n != name)
        asked = [r for r in d.delegations if r.outcome in ("answered", "reused")]
        asked_lines = "\n".join(f"- {r.from_agent} → {r.to_agent}: {r.question}" for r in asked) or "- none yet"
        return (
            "## Current situation\n"
            f"- You are `{name}`. Ticket: {d.ticket.id}. Shop date (desk.date_today): {d.date_today}.\n"
            f"- Delegation chain right now: {' → '.join(d.chain)} "
            f"(depth {d.depth} of max {MAX_DELEGATION_DEPTH}).\n"
            f"- Delegations used on this ticket: {len(d.delegations)} of {MAX_DELEGATIONS_PER_TICKET}.\n\n"
            f"## Teammates you can ask with `delegate_to`\n{others}\n\n"
            f"## Questions already asked on this ticket (reuse, don't repeat)\n{asked_lines}"
        )

    @agent.tool
    async def delegate_to(
        ctx: RunContext[TeamDeps],
        agent_name: AgentName,
        question: str,
        context: str,
        new_information: str | None = None,
    ) -> str:
        """Ask another Campus Customs agent one specific, unanswered question about this ticket.

        Args:
            agent_name: Who to ask: boss, inventory, accounting, facilities or customer_service.
            question: One specific question. Not "handle this ticket".
            context: The verified facts you already have (values and their sources), so they don't redo your work.
            new_information: Only when asking an agent that is already working on this ticket (e.g. the one that
                delegated to you): the new verified fact that makes this a genuinely different question.
        """
        d = ctx.deps
        me = d.me

        def refuse(reason: str) -> str:
            _record_delegation(d, DelegationRecord(from_agent=me, to_agent=agent_name, ticket_id=d.ticket.id,
                                                   question=question, depth=d.depth + 1, outcome="refused", note=reason))
            return f"DELEGATION REFUSED: {reason} Do not retry this request; answer with what you have and list the gap in limitations."

        if agent_name == me:
            return refuse("You cannot delegate to yourself.")
        if d.depth + 1 > MAX_DELEGATION_DEPTH:
            return refuse(f"Maximum delegation depth ({MAX_DELEGATION_DEPTH}) reached.")
        if len(d.delegations) >= MAX_DELEGATIONS_PER_TICKET:
            return refuse(f"This ticket already used {MAX_DELEGATIONS_PER_TICKET} delegations.")
        if agent_name in d.chain and not (new_information and new_information.strip()):
            return refuse(f"`{agent_name}` is already working on this ticket above you ({' → '.join(d.chain)}); "
                          "sending the task back would be circular. Return your findings instead.")

        key = (agent_name, _normalize(question))
        if key in d.answers:
            _record_delegation(d, DelegationRecord(from_agent=me, to_agent=agent_name, ticket_id=d.ticket.id,
                                                   question=question, depth=d.depth + 1, outcome="reused"))
            return f"(Already answered earlier on this ticket — reusing that answer.)\n{d.answers[key]}"

        prompt = (
            f"Ticket {d.ticket.id}. Question from `{me}`:\n{question}\n\n"
            f"Verified context from `{me}`:\n{context}\n"
        )
        if new_information:
            prompt += f"\nNew information since this was last discussed:\n{new_information}\n"
        prompt += f"\nTicket record (working database):\n{d.ticket.model_dump_json(indent=1)}"

        child = replace(d, chain=[*d.chain, agent_name])
        try:
            result = await run_agent(d.team.agents[agent_name], prompt, child, ctx.usage)
        except UsageLimitExceeded:
            raise  # the whole ticket is over budget: stop everything
        except Exception as exc:  # a failed teammate must not crash the caller
            log.exception("Delegation %s -> %s failed", me, agent_name)
            _record_delegation(d, DelegationRecord(from_agent=me, to_agent=agent_name, ticket_id=d.ticket.id,
                                                   question=question, depth=d.depth + 1, outcome="error",
                                                   note=type(exc).__name__))
            return f"DELEGATION FAILED: `{agent_name}` could not answer ({type(exc).__name__}). Report this limitation."

        answer = json.dumps(result.output.model_dump(mode="json"), ensure_ascii=False)
        d.answers[key] = answer
        _record_delegation(d, DelegationRecord(from_agent=me, to_agent=agent_name, ticket_id=d.ticket.id,
                                               question=question, depth=d.depth + 1, outcome="answered"))
        return answer

    @agent.output_validator
    def guard(ctx: RunContext[TeamDeps], out):
        """Hard checks on top of the prompts: right ticket, no claimed actions without a
        successful tool, drafts labelled, no negative-cash payment, no early closing."""
        d = ctx.deps
        if out.ticket_id != d.ticket.id:
            raise ModelRetry(f"ticket_id must be {d.ticket.id}.")

        ok_tools = {c.tool for c in d.tool_calls if c.ok}
        for a in out.actions:
            if a.status == "executed" and a.evidence_tool not in ok_tools:
                raise ModelRetry(
                    f"Action '{a.description}' is marked executed, but no successful call to "
                    f"'{a.evidence_tool}' happened on this ticket. Use recommended or awaiting_approval."
                )

        drafts: list[CustomerDraft] = []
        if isinstance(out, CustomerServiceReport):
            drafts = out.drafts
        elif isinstance(out, BossDecision) and out.customer_draft:
            drafts = [out.customer_draft]
        for draft in drafts:
            if "draft" not in f"{draft.subject} {draft.body}".lower():
                raise ModelRetry("Clearly label each customer message as a draft (in its subject or body).")

        if isinstance(out, AccountingReport):
            for p in out.payment_proposals:
                if p.projected_balance is not None and p.projected_balance < 0 and p.status != "refused":
                    raise ModelRetry(f"Payment '{p.reference}' would make cash negative; its status must be refused.")

        if isinstance(out, BossDecision) and out.ticket_status == "resolved":
            pending = [a for a in out.actions if a.status in ("recommended", "awaiting_approval")]
            if pending:
                raise ModelRetry(
                    "ticket_status can't be resolved while actions are still "
                    f"{', '.join(sorted({a.status for a in pending}))}. Use awaiting_approval, in_progress or blocked."
                )
        return out

    return agent
