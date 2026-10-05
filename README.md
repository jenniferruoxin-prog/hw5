# Campus Customs Multi-Agent Operations (HW5)

A class project (AI Foundations, Homework 5). An agent team runs the Campus Customs shop desk: tickets land on a board, and five PydanticAI agents — **Boss, Inventory, Accounting, Facilities, Customer Service** — work them, delegating to each other with full connectivity. A human watches on a React dashboard and approves every payment.

Three pieces talk to each other:

```
React board (frontend/, :5173)  →  FastAPI backend (backend/, :8000)  →  MCP server (mcp_server/, stdio)  →  data/campus_customs_new.db
                                         └─ 5 PydanticAI agents, gpt-6-luna via Portkey
```

- **Model:** every agent uses only `gpt-6-luna` through Portkey (`PORTKEY_API_KEY`). It's fixed in `backend/config.py`, with no fallback model.
- **Data:** all shop facts and every database change go through the MCP server, which only opens the working copy.
- **Payments:** agents can only *request* a payment. A human clicks Approve (`POST /api/approvals/{id}/approve`) to pay. Cash can never go negative.
- **Messages:** customer, vendor and landlord messages are drafts saved on the board. Nothing is ever sent.

## Layout

```
hw5/
├── AI_prompts.md              # prompt log, one section per problem
├── requirements.txt           # Python packages (MCP server + backend)
├── .env.example               # PORTKEY_API_KEY placeholder (copy to .env)
├── .gitignore
├── .mcp.json                  # registers the MCP server for Claude Code (vibe coder)
├── README.md
├── data/
│   ├── campus_customs.db      # ORIGINAL shop database — never modified (the reset point)
│   └── campus_customs_new.db  # WORKING copy — the MCP server reads/writes only this
├── mcp_server/
│   ├── server.py              # FastMCP server: 15 tools (12 agent tools + 3 human-only)
│   └── README.md
├── frontend/                  # React + Vite + TypeScript dashboard (the Ops Desk)
├── backend/
│   ├── main.py                # FastAPI routes for the dashboard
│   ├── models.py              # Pydantic data types (tickets, reports, decisions, deps)
│   ├── config.py              # model (gpt-6-luna), DB paths, loop limits
│   ├── audit.py               # append-only output/audit_trail.json
│   ├── agents/                # boss.py, inventory.py, accounting.py, facilities.py,
│   │                          # customer_service.py, base.py (delegation + guards), team.py (ticket loop)
│   └── prompts/               # shared_rules.md + boss.md, inventory.md, accounting.md,
│                              # facilities.md, customer_service.md
└── output/
    ├── harness.md             # how everything works: tables, tools, agents, routes, dashboard, safety
    ├── mcp_smoke.json         # Problem 4: MCP tool smoke test
    ├── desk_tickets.html      # Expected vs Actual per ticket, Cash, Reflection (double-click)
    ├── design.md              # dashboard design
    ├── resolved_tickets.json  # Problem 9 results per ticket
    ├── resolved_board.html    # screenshots of the resolved board (double-click)
    ├── resolved_board_images/ # the screenshots
    ├── audit_trail.json       # every agent loop step, delegation and human approval (append-only)
    └── github_url.txt
```

## Run it

**You need:** Python 3.12+ (tested on 3.14), Node.js 20+ (tested on 24), and a Portkey API key with access to `gpt-6-luna`.

### 1. Install and add your key

```bash
python -m venv .venv
source .venv/bin/activate          # Windows (PowerShell): .venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env               # then set PORTKEY_API_KEY=... in .env
```

`.env` can be in this folder or its parent folder. It's git-ignored, and only the backend reads it. Without a key, the board, tickets, cash and approvals still load; only agent runs fail.

### 2. Copy the original database to the working copy (clean run)

Both databases are in the repo. **The committed working copy holds the end state of our Problem 9 run** (three tickets resolved, checking $152.00). To start clean, copy the original over it:

```bash
cp data/campus_customs.db data/campus_customs_new.db          # Windows: copy data\campus_customs.db data\campus_customs_new.db
```

You can do the same thing with the **Reset database** button on the board, or with `POST http://localhost:8000/api/reset`. The original `campus_customs.db` is never written to. The MCP server refuses to open it.

### 3. Start the MCP server

```bash
python mcp_server/server.py
```

It runs over stdio and uses `data/campus_customs_new.db` (override with `CAMPUS_DB_PATH`).

- **For the app, you don't need to start it by hand.** The FastAPI backend starts its own copy as a subprocess when it boots.
- **For Claude Code:** `.mcp.json` registers it as `campus-customs`, so tools appear as `mcp__campus-customs__<tool>` when a session opens in this folder. `.mcp.json` points at `.venv/Scripts/python.exe` (Windows). On macOS/Linux, change it to `.venv/bin/python`.

### 4. Start the FastAPI backend (terminal 1)

```bash
cd backend
uvicorn main:app --reload --port 8000
```

Check it: http://localhost:8000/api/health should return `{"status":"ok","model":"gpt-6-luna",...}`. If a backend or MCP code change doesn't seem to apply, stop Uvicorn and start it again.

### 5. Start the React board (terminal 2)

```bash
cd frontend
npm install
npm run dev
```

This opens **http://localhost:5173**. The board calls the backend at `http://localhost:8000` (CORS allows the Vite origin). Use `?ticket=101` to open a ticket directly.

### 6. Full three-ticket run

1. **Reset the database first:** press **Reset database** on the board (or step 2). Checking goes back to **$3,400.00** and tickets 101, 102 and 103 go back to `open`.
2. Pick a ticket in the **Desk Queue** and press **Start team**. Watch the Team Feed and Agent roster.
3. When Accounting asks for a payment, the amber **Human decision required** panel appears. Type your name and approve or reject. Only this human click moves cash.
4. Press **Start team again** so the agents can verify the payment and close the ticket. A ticket shows as resolved only when the backend reports it.
5. If the team needs a business call (e.g. which discount to offer, or what counts as done), record it with `POST /api/tickets/{id}/decision` with body `{"decided_by": "Your Name", "decision": "..."}`, then run the ticket again.

The run we did, with all the numbers, is in `output/desk_tickets.html` (Actual and Cash tabs), `output/resolved_tickets.json` and `output/harness.md` §9.

## Safety notes

- No real customer data. The databases are the course's test data. Approvals in the audit trail are by the student (Jennifer Zhang) acting as the human manager.
- The repo has no API key. `.env` is git-ignored, and `.env.example` holds only a placeholder.
- Nothing is sent anywhere. There are no email, phone or payment-provider integrations, and all messages stay drafts on the board.

## Documentation

- [output/harness.md](output/harness.md): **start here.** Tables, all MCP tools and the tables they use, the five agents, loop limits, audit trail, safety rules, API routes, dashboard, and the full-run results.
- [output/desk_tickets.html](output/desk_tickets.html): Expected vs Actual per ticket, the Cash itemization, and the Reflection.
- [output/design.md](output/design.md): dashboard design.
- [mcp_server/README.md](mcp_server/README.md): the MCP tools.
- [AI_prompts.md](AI_prompts.md): the prompts used to build this project, problem by problem.
