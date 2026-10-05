# Campus Customs Multi-Agent Operations — Harness

How the whole system works: data, agents, tools, safety and specs. This file grows problem by problem.

## 1. Data

### 1.1 Files

| File | Role |
|---|---|
| `data/campus_customs.db` | The original shop database from the course. **Never written to.** Copy it again to reset. |
| `data/campus_customs_new.db` | The working copy. The MCP server and backend read and write **only** this file. |

**Reset before every full run:** copy `campus_customs.db` over `campus_customs_new.db` so every run starts from the original values.

### 1.2 Tables

All 9 tables, their fields, and why each matters to the agents. Row counts are from the original file.

#### `desk` (1 row) — the shop's clock
| Field | Type | Note |
|---|---|---|
| `date_today` | TEXT | "Today" for the shop (`2026-08-31`). |
| `notes` | TEXT | Free-text desk note (empty). |

**Why it matters:** every agent uses `date_today`, not the computer's clock, to decide what is overdue, what is due soon and when a restock would arrive.

#### `tickets` (3 rows) — the work queue
| Field | Type | Note |
|---|---|---|
| `id` | INTEGER PK | Ticket number (101–103). |
| `type` | TEXT | `customer_order`, `rent_notice`, `price_override`. |
| `requester` | TEXT | Who asked: a customer, a landlord or a student org. |
| `subject` | TEXT | Short title. |
| `sku`, `size`, `qty` | TEXT, TEXT, INTEGER | The item asked for, if any. Links to `inventory` and `pricing`. |
| `lease_id` | INTEGER FK → `leases.id` | Set on rent tickets. |
| `invoice_id` | INTEGER FK → `invoices.id` | Set when a vendor bill blocks the ticket. |
| `status` | TEXT | `open` to start. Agents move it to resolved, or to waiting on a human. |
| `notes` | TEXT | The request in the requester's words. |
| `created_at` | TEXT | ISO timestamp the ticket arrived. |

**Why it matters:** this is the board. Boss reads each open ticket and routes it, and the link fields tell each agent which other tables to look at.

#### `inventory` (10 rows) — stock on hand
| Field | Type | Note |
|---|---|---|
| `sku` | TEXT | Product code. PK with `size`. |
| `name` | TEXT | Product name. |
| `size` | TEXT | S/M/L/XL, or `OS` (one size). |
| `qty` | INTEGER | Units on the shelf. |
| `location` | TEXT | Aisle. |

**Why it matters:** Inventory checks stock here by SKU and size, and works out any shortfall (amount asked − `qty`).

#### `pricing` (4 rows) — cost and price per SKU
| Field | Type | Note |
|---|---|---|
| `sku` | TEXT PK | Product code. |
| `unit_cost` | REAL | What the shop pays per unit. |
| `list_price` | REAL | Normal selling price. |

**Why it matters:** Accounting uses it to check margins on discount requests (a price can't drop below `unit_cost`) and to cost purchase orders.

#### `vendors` (3 rows) — who can restock
| Field | Type | Note |
|---|---|---|
| `id` | INTEGER PK | Vendor id. |
| `name` | TEXT | Vendor name. |
| `specialty` | TEXT | What they supply (`apparel reprint`, `mugs and small goods`, `local courier`). |
| `lead_days` | INTEGER | Days from order to delivery. |

**Why it matters:** Inventory picks a vendor by `specialty` and works out the arrival date as `date_today + lead_days`. There's no SKU→vendor link, so the match is by product type.

#### `invoices` (1 row) — bills the shop owes
| Field | Type | Note |
|---|---|---|
| `id` | INTEGER PK | Invoice number. |
| `vendor_id` | INTEGER FK → `vendors.id` | Who is owed. |
| `amount` | REAL | Amount due. |
| `due_date` | TEXT | Overdue if before `desk.date_today`. |
| `status` | TEXT | `open` (unpaid) or `paid`. |
| `description` | TEXT | What it was for. |

**Why it matters:** **a vendor won't ship new product while it still has an open, unpaid invoice.** Accounting must see this before any restock is promised.

#### `leases` (1 row) — the shop space
| Field | Type | Note |
|---|---|---|
| `id` | INTEGER PK | Lease id. |
| `space_name` | TEXT | The store location. |
| `landlord` | TEXT | Who is paid rent. |
| `monthly_rent` | REAL | Rent amount. |
| `next_due` | TEXT | Next rent due date. |
| `notes` | TEXT | Free text. |

**Why it matters:** Facilities owns this table. Rent is the largest single payment, and `next_due` moves forward one month once rent is paid.

#### `cash_accounts` (1 row) — money available
| Field | Type | Note |
|---|---|---|
| `name` | TEXT PK | Account name (`checking`). |
| `balance` | REAL | Cash on hand (`3400.00`). |
| `date` | TEXT | As-of date. |

**Why it matters:** the pay tool checks this before every payment and **refuses if the balance would go negative**. Cash only goes out in this homework, since no revenue is modelled.

#### `payments` (0 rows) — payment record
| Field | Type | Note |
|---|---|---|
| `id` | INTEGER PK | Payment id. |
| `kind` | TEXT | What was paid: `invoice`, `rent` or `purchase_order`. |
| `ref_id` | INTEGER | The invoice, lease or PO id it pays. |
| `amount` | REAL | Amount paid. |
| `account` | TEXT | Which `cash_accounts.name` it came from. |
| `paid_at` | TEXT | When it was paid. |
| `approved_by` | TEXT | The **human** who approved it. Required, so no payment exists without approval. |

**Why it matters:** each approved payment adds a row here and, in the same transaction, lowers `cash_accounts.balance` and closes the linked invoice or moves the lease's `next_due`.

### 1.3 How the three open tickets link to other tables

Today is **2026-08-31**. Checking balance is **$3,400.00**.

**Ticket 101 — `customer_order`, Tauhid Zaman: 1 × Classic Bulldog Tee, size S**
- `inventory` CC-TEE-WHITE / S → **qty 0**, a shortfall of 1.
- Apparel restock vendor is Bulldog Print Co (vendor 1, `lead_days` 5).
- `invoice_id` 501 → invoice to vendor 1, **$840, due 2026-08-28, status open: 3 days overdue**. Bulldog Print Co won't ship until it's paid.
- Path: Accounting asks a human to approve paying invoice 501 → the vendor can reprint → the tee arrives about 5 days after ordering. Customer Service drafts an update for the customer (left on the board, not sent).
- Pricing: cost $8, list $28.

**Ticket 102 — `rent_notice`, Elm City Properties: rent due**
- `lease_id` 1 → Chapel Street shop, **$2,400**, `next_due` **2026-09-02** (due in 2 days, not overdue yet).
- Path: Facilities confirms the lease → Accounting checks cash → a human approves → pay, then `next_due` moves to 2026-10-02.

**Ticket 103 — `price_override`, Yale AI Club: 20 × Basic Hoodie, size M, bulk discount**
- `inventory` CC-HOOD-NAVY / M → **qty 8**, a shortfall of 12 (other sizes don't count).
- `pricing`: cost $22, list $58. Margin at list is $36/unit (62%). Any discount must stay above $22.
- Restock would also come from Bulldog Print Co, which is blocked by invoice 501 too.
- Path: Inventory reports the shortfall → Accounting sets a discount floor and costs a PO for 12 → Boss decides → Customer Service drafts a reply.

**Cash check across all three:** invoice 501 ($840) + rent ($2,400) = $3,240, leaving **$160**. A 12-hoodie PO at cost (12 × $22 = $264) wouldn't fit after both, so the agents must put payments in order of priority and can't promise everything at once. The pay tool will refuse anything that would make the balance negative.

## 2. Model

Every agent uses **only `gpt-6-luna` through Portkey** (`PORTKEY_API_KEY` from the root `.env`). No other model may appear in code or runs.

## 3. MCP tools

Server: `mcp_server/server.py` (FastMCP). It reads `data/campus_customs_new.db` only, in read-only mode for these three tools; §3.2 lists every tool now on the server. All dates are measured from `desk.date_today`. Unknown keys raise an error instead of a guess. See [mcp_server/README.md](../mcp_server/README.md).

| Tool | Reads | Unlocks | Why it's the right tool |
|---|---|---|---|
| `check_vendor_shipping(vendor_id=None)` | `vendors`, `invoices`, `desk` | **101**: Tauhid's size S Bulldog tee | The S tee has 0 on the shelf, so the order depends on a reprint from Bulldog Print Co, and this tool shows that vendor is blocked by its own open invoice 501 ($840, 3 days overdue), so it won't ship until Accounting gets that bill approved and paid, after which the 5-day lead time sets the earliest date we can promise Tauhid. |
| `get_rent_due(lease_id)` | `leases`, `desk` | **102**: Elm City Properties rent notice | The ticket only says "rent due in 2 days", and this tool turns its `lease_id` 1 into the exact amount ($2,400), payee (Elm City Properties) and due date (2026-09-02, 2 days after `date_today`, so not yet overdue) that Facilities and Accounting need before asking a human to approve the payment. |
| `check_stock_and_price(sku, size, qty_needed)` | `inventory`, `pricing` | **103**: Yale AI Club's 20 size-M hoodies at a bulk discount | Called with CC-HOOD-NAVY, M, 20, it shows only 8 on hand (a shortfall of 12) and a $22 unit cost against a $58 list price, which tells the Boss both how many hoodies the club can get now and the lowest discounted price that still makes money. |

Checked by calling each tool in memory through a FastMCP `Client` on 2026-10-04. The outputs matched the database above, and both database files stayed byte-identical afterwards.

### 3.1 Connection and smoke test

- **Connection:** `.mcp.json` at the HW5 root registers the stdio server `campus-customs`, which runs `.venv/Scripts/python.exe mcp_server/server.py` with `CAMPUS_DB_PATH=data/campus_customs_new.db`. Claude Code loads it when a session opens in HW5, and the tools appear as `mcp__campus-customs__<tool>`.
- **Smoke test:** [mcp_smoke.json](mcp_smoke.json) records one call per tool, made through that connection. Each entry has the prompt, the tool name, the input, the exact output, and a field-by-field comparison with `campus_customs_new.db`. All values matched, no payment was created, and the working copy is still identical to the original.

### 3.2 All MCP tools (current)

The three tools above unlocked the read side of each ticket. Problem 5 added the tools the agents need to finish the tickets: read the board, check cash and invoices, ask for payment approval, save drafts and set ticket status. All shop facts and every database change go through this one MCP server. The backend never opens the database itself.

To hold the approval queue and the drafts, the server adds two **board tables** to the working copy only (`CREATE TABLE IF NOT EXISTS`, so the original's 9 tables are unchanged, and the server refuses to open `campus_customs.db`):
- `approval_requests`: id, ticket_id, kind, ref_id, payee, amount, details (JSON), requested_by, reason, status (pending/approved/rejected), created_at, decided_by, decided_at, decision_note, payment_id.
- `board_notes`: id, ticket_id, kind (draft/status), author, recipient, subject, body, created_at.

| # | Tool | Tables read → **written** | Who can call it | What it does |
|---|---|---|---|---|
| 0 | `list_tickets()` | tickets, desk, invoices, leases | all agents (and `GET /api/tickets`) | All tickets, open and resolved, with `is_resolved` and an `urgency` fact (linked invoice or lease due date vs `desk.date_today`), added for the dashboard. |
| 1 | `list_open_tickets()` | tickets, desk | all agents | The board: every ticket not yet resolved. |
| 2 | `get_ticket(ticket_id)` | tickets, desk, board_notes, approval_requests | all agents (and the backend, to start a run) | One ticket plus its drafts, status notes and approval requests. |
| 3 | `update_ticket_status(ticket_id, status, note, author)` | tickets, approval_requests → **tickets.status, board_notes** | all agents (the Boss sets final status) | Moves a ticket to open / in_progress / awaiting_approval / blocked / resolved, with a note. **Refuses `resolved` while a payment request is pending.** |
| 4 | `save_draft(ticket_id, recipient, subject, body, author)` | tickets → **board_notes** | all agents (Customer Service) | Saves a message draft on the board. Nothing is sent, and the server has no email or phone channel. |
| 5 | `check_stock_and_price(sku, size, qty_needed)` | inventory, pricing | all agents | Stock for one SKU and size, the shortfall, unit cost, list price, margin. |
| 6 | `check_vendor_shipping(vendor_id?)` | vendors, invoices, desk | all agents | Lead days, open invoices, `can_ship`, earliest arrival. |
| 7 | `get_rent_due(lease_id)` | leases, desk, payments, approval_requests | all agents | Rent, landlord, next due date, days until due or overdue, plus the rent payments already recorded on the lease and the due date each one covered. That last part was added during the Problem 9 run: without it the agents couldn't tell that `next_due` had moved forward because the rent was paid. |
| 8 | `get_cash_balance(account?)` | cash_accounts, desk, approval_requests | all agents | Balance, total pending approval, and the balance if every pending request is approved. |
| 9 | `get_invoice(invoice_id)` | invoices, vendors, payments, approval_requests, desk | all agents | Invoice amount, status, due status, plus payments and requests already on it (duplicate check). |
| 10 | `list_payments(kind?, ref_id?)` | payments | all agents | Payments already made, to check for duplicates or confirm a payment was recorded. |
| 11 | `request_payment_approval(ticket_id, kind, ref_id, requested_by, reason, sku?, size?, qty?)` | invoices, leases, vendors, inventory, pricing, payments, cash_accounts, approval_requests → **approval_requests** | all agents (Accounting) | Puts a **pending** request on the board. **No money moves.** The amount and payee are looked up by the tool, not typed by the agent. Refused if the reference is missing, already paid or already requested, the vendor is blocked (purchase orders), or cash − pending − this < $0. |
| 12 | `list_approval_requests(status?, ticket_id?)` | approval_requests, payments | all agents | The approval queue. An approved and paid purchase order also shows `order_status: placed`, `order_placed_on` and `expected_arrival` (payment date + vendor lead days), worked out when it's read; `get_ticket` shows the same. |
| 13 | `approve_payment(request_id, approver, account?)` | approval_requests, cash_accounts, invoices, leases, vendors → **payments, cash_accounts, invoices.status or leases.next_due, approval_requests** | **human only** | Re-checks cash (refuses if the balance would go negative), then in one transaction records the payment with `approved_by` = the human, lowers the balance, and marks the invoice paid or moves `next_due` forward one month. |
| 14 | `reject_payment(request_id, approver, reason)` | approval_requests → **approval_requests** | **human only** | Rejects a pending request. No money moves. |
| 15 | `record_human_decision(ticket_id, decided_by, decision)` | tickets → **board_notes** (kind `human_decision`) | **human only** | Puts a manager's decision on the ticket (an authorized discount, or what counts as done). Agents read it through `get_ticket`. No money moves. Added in Problem 9. |

**Human-only tools:** the backend filters `approve_payment`, `reject_payment` and `record_human_decision` out of every agent's tool list. They're called only by `Team.approve_payment()` / `Team.reject_payment()` / `Team.record_decision()` on behalf of a named person, through the dashboard or the API. As a second lock, the server refuses an approver that is an agent name or contains "agent".

**Checked offline on 2026-10-04** on a scratch copy of the database (the working copy was not touched):
- A purchase order to Bulldog Print Co is refused while invoice 501 is open.
- Requesting invoice 501 projects $2,560. A duplicate request is refused.
- Requesting rent projects $160.
- Resolving ticket 101 with a pending request is refused, and so is an agent acting as approver.
- A human approving 501 makes cash $3,400 → $2,560 and marks the invoice paid. Approving it again is refused.
- A 12-hoodie purchase order ($264) is then refused because −$104 would be negative.
- Approving rent makes cash $2,560 → $160 and moves `next_due` from 2026-09-02 to 2026-10-02.
- `payments` holds 2 rows, each with `approved_by`.

## 4. Agent team (PydanticAI)

Five agents, all on **`gpt-6-luna` via Portkey**. The model is set once in `backend/config.py`, isn't read from the environment, and has no fallback.

| Agent | Code | Prompt (your words) | Output type | Main MCP tools it uses |
|---|---|---|---|---|
| **Boss** | `backend/agents/boss.py` | `prompts/boss.md` | `BossDecision` | `get_ticket`, `list_open_tickets`, `update_ticket_status`, `list_approval_requests` |
| **Inventory** | `backend/agents/inventory.py` | `prompts/inventory.md` | `InventoryReport` | `check_stock_and_price`, `check_vendor_shipping` |
| **Accounting** | `backend/agents/accounting.py` | `prompts/accounting.md` | `AccountingReport` | `get_cash_balance`, `get_invoice`, `list_payments`, `check_stock_and_price`, `request_payment_approval`, `list_approval_requests` |
| **Facilities** | `backend/agents/facilities.py` | `prompts/facilities.md` | `FacilitiesReport` | `get_rent_due` |
| **Customer Service** | `backend/agents/customer_service.py` | `prompts/customer_service.md` | `CustomerServiceReport` | `save_draft`, plus read tools to check facts |

- **Tools:** every agent can see all 13 agent tools plus `delegate_to`. The 3 human-only tools are hidden. Its prompt decides which ones fit its role. None of them can see `approve_payment` or `reject_payment`.
- **Prompts:** each agent's instructions are `prompts/shared_rules.md` plus its role file, both in the user's own words. The code adds only a short block of run details at the start of each run: ticket ID, `desk.date_today`, the delegation chain, the teammate list and questions already asked.
- **Data types** (`backend/models.py`):
  - `Ticket` and `Finding`
  - `Action`, with status recommended / awaiting_approval / executed / refused / resolved
  - the role reports
  - `PaymentProposal`: only `awaiting_approval` or `refused`
  - `MarginCheck` and `LeaseStatus`
  - `CustomerDraft`: always `draft`
  - `BossDecision` and `TicketRun`
  - `TeamDeps`: per-ticket shared state with the run ID, delegation chain, tool-call log and answer cache
- **Agent loop:** `Team.run_ticket(id)` (`backend/agents/team.py`) loads the ticket with the MCP tool `get_ticket` and runs the Boss. Any agent can call any other with `delegate_to` (**full connectivity**). Every agent loop runs step by step through `run_agent()` (`agents/base.py`), which writes each step to the audit trail.
- **Delegation guards:**
  - No delegating to yourself.
  - No sending a task back up the chain unless `new_information` is given.
  - The same question to the same agent reuses the earlier answer.
  - Depth is capped at 3 and delegations at 10 per ticket.
  - A refused delegation tells the agent to report the gap to the Boss.
- **Output guards** (the model must retry):
  - `ticket_id` must match.
  - An `executed` action must name an MCP tool that succeeded on this ticket.
  - A payment that would make cash negative must be `refused`.
  - Customer messages must be labelled as drafts.
  - The Boss can't return `resolved` while actions are recommended or awaiting approval.
- **Status on the board:** the Boss normally sets the ticket status itself with `update_ticket_status`. If it didn't, `Team.run_ticket` writes the Boss's final `ticket_status` through the same MCP tool after the run (audit event `status_sync`), and the server still refuses `resolved` while a payment is pending.
- **Human decisions:** when a ticket needs a business call the agents may not make (a discount with no policy, or what "done" means when delivery is after the shop date), the Boss waits (`blocked` or `awaiting_approval`). A manager then records a decision with `record_human_decision`, and the next run applies it.
- **Reset:** `agents.team.reset_working_db()` (or `POST /api/reset`) copies `campus_customs.db` over `campus_customs_new.db`. Run it before every full run.

## 5. Audit trail

`output/audit_trail.json` is one JSON array, **appended to and never wiped** (`backend/audit.py`). Each record is written to disk as it happens, so a crash still keeps the earlier steps. A corrupt file is moved aside, not deleted. Each record has `time`, `event`, `run_id` and `ticket_id`, and for agent steps also `agent`, `chain`, `depth` and `step`.

| Event | When | What it records |
|---|---|---|
| `ticket_start` / `ticket_end` | each ticket run | ticket row, `date_today`, model; at the end the ticket status, error, delegations, MCP calls (and how many failed), total usage |
| `agent_start` | each agent loop begins | the prompt the agent received, model |
| `model_request` | each loop step, going **into** the model | tool results (tool name, call ID, content), retry messages |
| `model_response` | each loop step, coming **out of** the model | text, tool calls (name and args, including `delegate_to` and the final-output call), model name, tokens |
| `agent_end` / `agent_error` | each agent loop ends | number of steps, full structured output (or the error), ticket usage so far |
| `delegation` | every `delegate_to` | from, to, question, depth, outcome (answered / reused / refused / error) and why |
| `human_approval` / `human_rejection` | a human decides a payment | request ID, approver, result (cash before and after, payment ID) or the refusal |
| `database_reset` | working copy reset | from and to file names |
| `human_decision` | a manager records a decision on a ticket | ticket, who decided, the decision text |
| `status_sync` | after a run, if the board status differs from the Boss's final status | the status written (or why the server refused it) |

Long texts are cut at 4,000 characters. No API key or secret is ever in a message.

## 6. Safety

### Guardrails a real business would want (and where this project has them)
- **A human approves every payment.** Agents can only create a *pending* request. Paying is a separate human-only tool, hidden from agents and refusing agent names as approver. In production that tool would sit behind real sign-in (SSO) on a separate server, with the approver's identity taken from the login and not from a text field.
- **The tool decides money amounts, not the model.** The amount comes from the invoice, the lease, or qty × `unit_cost`, so a model can't type a wrong or inflated amount. Payee and amount are shown to the human before approval.
- **No negative cash, checked twice:** at request time (cash − all pending − this one) and again at approval, inside a locked transaction so two approvals can't race.
- **No duplicate payments:** an invoice can't be requested or paid twice, and rent can be paid only once per due date.
- **Vendor block enforced in code:** no purchase order to a vendor with an open invoice.
- **No outside contact:** the MCP server has no email, phone or vendor channel. Customer and vendor messages are board drafts, and the prompt also forbids revealing cash, invoice disputes or private data in them.
- **Least privilege and a safe reset point:** reads open the database read-only, and every write is one transaction. The original database can't be opened by the server and is restored with `reset_working_db()`.
- **No made-up "done":** an action can't be marked executed without a successful tool call, a ticket can't be resolved with a payment still pending (checked both in the server and in the output guard), and the full audit trail allows review after the fact.
- **Real-world extras worth adding:** spending limits per approver and two-person approval above a set amount, fraud checks when a vendor's bank details change, alerts on refused or failed tool calls, PII redaction in the audit log for real customers, and a kill switch that pauses all agents.

### Shop rules enforced in this project (summary)

| Rule | Where it's enforced |
|---|---|
| Every payment needs human approval | Agents only have `request_payment_approval` (pending). `approve_payment` is human-only: hidden from agents and refusing agent names. Every `payments` row has `approved_by`. |
| No negative cash; cash only goes out | `request_payment_approval` checks cash − pending − this one; `approve_payment` re-checks inside a locked transaction. No tool adds money. |
| A vendor with an open invoice won't ship | `check_vendor_shipping` reports `can_ship=false`; `request_payment_approval` refuses a purchase order to that vendor. |
| `desk.date_today` is today | Every date tool measures from it, not the computer clock. |
| Never touch the original database | The server refuses `campus_customs.db`; reset copies the original over the working copy. |
| No contact with customers or vendors | No email, phone or vendor channel exists. Messages are `save_draft` board notes. |
| No invented values or actions | Amounts come from the database; an output guard rejects an `executed` action without a successful tool call; tickets can't be resolved with a payment pending. |
| Business decisions belong to people | Discounts without a policy, and changes to what "done" means, wait for `record_human_decision`. |
| One model only | `gpt-6-luna` is hard-coded in `config.py`, with no fallback. |

### Limits that keep token use in check
- **One model:** `gpt-6-luna` only, with no fallback.
- **Per-ticket budget, shared by every agent in the chain:** 40 model requests, 40 tool calls, 300,000 total tokens (`TICKET_LIMITS`). When it's hit, the run stops and records a `ticket_end` with the error, instead of looping.
- **Delegation limits:** max depth 3, max 10 delegations per ticket. Circular hand-backs are blocked, and repeated questions reuse the earlier answer without a new model call.
- **Retries:** at most 2 output-validation retries per agent run.
- **Tight context:** each delegation passes a specific question plus verified context, not the whole history. Long tool output in the audit is clipped.
- **Tickets are run one at a time on request**, never on a timer, so nothing burns tokens in the background.

## 7. Backend API (FastAPI, `backend/main.py`)

Start it from `backend/` with `uvicorn main:app --reload --port 8000`; it then serves http://localhost:8000. CORS allows the Vite dashboard on port 5173. All data comes through the MCP server, and `main.py` never opens the database.

- `GET /api/health`: server is up, the model name (`gpt-6-luna`), how many runs are in progress.
- `GET /api/tickets`: all three tickets with their status and `board_state` (open / resolved), and whether a run is going on now.
- `GET /api/tickets/{id}`: one ticket with its board drafts, status notes and approval requests.
- `POST /api/tickets/{id}/run`: starts the agent team on that ticket in the background and returns a `run_id` at once (409 if a run is already going, so a double click can't spend tokens twice).
- `GET /api/runs` and `GET /api/runs/{run_id}`: status of dashboard runs (running / done / error) and the Boss's final decision.
- `GET /api/events?since=&ticket_id=&run_id=&since_reset=`: recent agent events from `output/audit_trail.json`, i.e. what each agent said, which tools it called (with arguments) and what they returned, plus delegations and human decisions. Use `next_since` to fetch only new events when the board refreshes. `since_reset=true` skips events from before the last database reset.
- `POST /api/tickets/{id}/decision` (body `{"decided_by", "decision"}`): a manager records a decision on the ticket (human-only tool `record_human_decision`). Refuses agent names.
- `GET /api/approvals?status=pending`: the payment and purchase-order requests the agents prepared, waiting for a human.
- `POST /api/approvals/{id}/approve` (body `{"approver": "Full Name"}`): **a human clicked Approve**. This is the only route that moves cash: it records the payment, lowers the balance, and marks the invoice paid or moves the rent due date. It refuses agent names, already-decided requests and anything that would make cash negative.
- `POST /api/approvals/{id}/reject` (body `{"approver", "reason"}`): a human rejects a request. No money moves.
- `GET /api/cash`: the current `checking` balance from `cash_accounts`, plus pending approvals and the balance if all of them were approved.
- `POST /api/reset`: copies the original `campus_customs.db` over `campus_customs_new.db` for a fresh run (refused while a run is going). The audit trail is kept.

**Checked on 2026-10-04:**
- In-process on a scratch database: every route answered. An agent-name approver got 400, the human approval paid $840 (cash $3,400 → $2,560), a second approval got 400, and an unknown ticket got 400.
- Live with `uvicorn --reload --port 8000`: health, tickets, cash, events and reset all answered, and the working copy matched the original afterwards. No agent run was started, so no model calls were made.

## 8. Dashboard (React + Vite + TypeScript, `frontend/`)

Start it with `cd frontend && npm run dev` (http://localhost:5173). It calls the backend at `http://localhost:8000`, set in `src/api.ts` and overridable with `VITE_API_URL`; the backend's CORS allows the Vite origin. The look and the reasons for it are in [design.md](design.md).

- **Desk Queue (left):** tickets shown as print-shop job slips with status, a preview, and an urgency fact from the linked invoice or lease due date. Resolved tickets move into a ✓ Resolved group.
- **Workbench (center):**
  - the ticket and **Start team**
  - the amber **Human decision required** panel: payee, amount, related invoice, lease or purchase, reason, cash now and after, Approve / Reject
  - the **Team Feed**: each entry shows agent, role, time and a label (Briefed, Delegating, Checking data, Data returned, Recommendation, Completed)
  - the **Final summary**: the Boss's call, one card per agent that took part (all runs on the ticket since the last reset), and the latest unsent draft
- **Operations (right):** checking balance (previous → payment → now after an approval), Needs attention, Agent roster with live status, backend connection.
- **Data:** it polls `/api/tickets`, `/api/cash` and `/api/approvals` every 4 s, and `/api/events` every 1 s while a run is going. A ticket shows as resolved only when the backend says so.
- **Deep link:** `?ticket=101` opens a ticket directly; this is how the screenshots in `resolved_board.html` were taken.

## 9. Full run (Problem 9)

The database was reset first: starting checking **$3,400.00**. The team ran 12 times across the 3 tickets, all on `gpt-6-luna`: 132 model requests and about 527k tokens in total. There were 0 failed tool calls and 1 refused (circular) delegation. Every run is in `audit_trail.json`.

| Ticket | Runs | Human actions (Jennifer Zhang) | Cash | Final |
|---|---|---|---|---|
| 101 Bulldog tee | 5 | Approved #1 invoice 501 ($840) and #3 tee purchase order ($8); decided what counts as done (order placed and paid, arrival recorded, draft saved) | −$848.00 | resolved |
| 102 Rent due | 3 | Approved #2 rent ($2,400) | −$2,400.00 | resolved |
| 103 Hoodie discount | 4 | Decided: offer the 8 in-stock hoodies at 10% off ($52.20), no restock; then decided what counts as done | $0.00 | resolved |

Ending checking **$152.00**, which matches `cash_accounts` in `campus_customs_new.db`. The original database is unchanged. Results: [desk_tickets.html](desk_tickets.html) (Expected vs Actual, Cash), [resolved_tickets.json](resolved_tickets.json), [resolved_board.html](resolved_board.html).

**What the run taught us, and the fixes made during it:**
1. Paying rent moves `next_due`, so on the next run the agents saw a "mismatch" with the notice → `get_rent_due` now lists rent payments and the due date each one covered.
2. A paid purchase order had no "order placed" record → approved purchase orders now show their order status and expected arrival.
3. Some calls belong to people (a discount with no policy, what "done" means when delivery is after the fixed shop date). The agents correctly refused to guess → added `record_human_decision`.
4. The dashboard double-counted events because React runs some effects twice in development → events are now merged by audit index.
