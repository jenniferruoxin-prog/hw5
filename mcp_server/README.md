# Campus Customs Ops — MCP server

**What it's for:** this is the one shared toolbox for the whole agent team (Boss, Inventory, Accounting, Facilities, Customer Service). Agents and the backend never touch the database directly. Every shop fact (stock, vendors, cash, invoices, rent, tickets) and every change (approval requests, drafts, ticket status, approved payments) goes through these tools. Built with [FastMCP](https://gofastmcp.com).

**Database:** `data/campus_customs_new.db`, the working copy. The server refuses to open the original `data/campus_customs.db`, so you can reset by copying the original over the working copy. You can point the server at another file with `CAMPUS_DB_PATH`. "Today" for every date check is `desk.date_today`, not the real calendar. The server adds two board tables to the working copy only: `approval_requests` and `board_notes`.

## Tools

| Tool | Tables | What it does |
|---|---|---|
| `list_tickets()` | tickets, desk, invoices, leases | All tickets, open and resolved, with `is_resolved` and an `urgency` due-date fact from the linked invoice or lease. |
| `list_open_tickets()` | tickets, desk | Every ticket not yet resolved. |
| `get_ticket(ticket_id)` | tickets, desk, board_notes, approval_requests | One ticket plus its drafts, status notes and approval requests. |
| `update_ticket_status(ticket_id, status, note, author)` | tickets, board_notes, approval_requests | Sets the status with a note. Refuses `resolved` while a payment request is pending. |
| `save_draft(ticket_id, recipient, subject, body, author)` | board_notes | Saves a message draft on the board. Nothing is sent. |
| `check_stock_and_price(sku, size, qty_needed=1)` | inventory, pricing | Stock on hand, shortfall, unit cost, list price, margin. |
| `check_vendor_shipping(vendor_id=None)` | vendors, invoices, desk | Lead days, open invoices, whether the vendor can ship, earliest arrival. |
| `get_rent_due(lease_id)` | leases, desk, payments, approval_requests | Rent, landlord, next due date, days until due or overdue, and the rent payments already made with the due date each covered. |
| `get_cash_balance(account="checking")` | cash_accounts, approval_requests | Balance, pending approvals, balance if all are approved. |
| `get_invoice(invoice_id)` | invoices, vendors, payments, approval_requests | Invoice details, due status, and payments or requests already on it. |
| `list_payments(kind=None, ref_id=None)` | payments | Payments already made (duplicate check). |
| `request_payment_approval(ticket_id, kind, ref_id, requested_by, reason, sku?, size?, qty?)` | approval_requests (+ reads invoices, leases, vendors, pricing, payments, cash_accounts) | Creates a **pending** request for a human. No money moves. The amount is looked up, not typed. Refuses duplicates, blocked vendors and anything that would make cash negative. |
| `list_approval_requests(status=None, ticket_id=None)` | approval_requests | The approval queue. |
| `approve_payment(request_id, approver)` — **human only** | approval_requests, payments, cash_accounts, invoices, leases | Re-checks cash, then in one transaction pays: adds a `payments` row (`approved_by` = the human), lowers the balance, and marks the invoice paid or moves the lease's `next_due` forward one month. |
| `reject_payment(request_id, approver, reason)` — **human only** | approval_requests | Rejects a pending request. |
| `record_human_decision(ticket_id, decided_by, decision)` — **human only** | board_notes | Puts a manager's decision on a ticket's board (authorized discount, what counts as done). Agents read it through `get_ticket`. |

**Safety:**
- Read tools open the database read-only, and every write tool is a single transaction.
- Unknown IDs raise an error rather than a guess.
- The backend hides the three human-only tools from every agent.
- `approve_payment`, `reject_payment` and `record_human_decision` also refuse an agent name.

## Run

```bash
pip install -r requirements.txt
python mcp_server/server.py
```

It runs over stdio. Claude Code connects through `.mcp.json` (server `campus-customs`), and the backend starts it as a subprocess (`backend/agents/team.py`).
