"""Campus Customs operations MCP server (FastMCP).

Every agent on the team gets its shop facts through these tools. The server only
talks to the working copy data/campus_customs_new.db; it refuses to open the
original data/campus_customs.db, so that file stays a clean reset point.

Tools return only what is in the database. If a SKU, vendor, lease, invoice or
ticket is not found, the tool raises an error instead of guessing. Money amounts
for payments are always looked up by the tool (invoice amount, monthly rent,
qty x unit_cost), never typed in by an agent.

Payment flow (human approval required):
  agent  -> request_payment_approval  (creates a *pending* approval request; no money moves)
  human  -> approve_payment / reject_payment  (HUMAN-ONLY tools; the backend hides them from agents)
  approve_payment re-checks cash, then in one transaction writes payments, lowers
  cash_accounts.balance, and marks the invoice paid / moves the lease's next_due.

Run:  python mcp_server/server.py   (stdio)
"""

from __future__ import annotations

import calendar
import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Iterator, Literal

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

HW5_DIR = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.getenv("CAMPUS_DB_PATH", HW5_DIR / "data" / "campus_customs_new.db"))
if not DB_PATH.is_absolute():
    DB_PATH = HW5_DIR / DB_PATH
ORIGINAL_DB_NAME = "campus_customs.db"

READ_ONLY = {"readOnlyHint": True, "openWorldHint": False}
WRITES = {"readOnlyHint": False, "destructiveHint": False, "openWorldHint": False}
HUMAN_ONLY = {"readOnlyHint": False, "destructiveHint": True, "openWorldHint": False}

# Tools only a human (through the dashboard/backend) may call. The backend filters these
# out of every agent's tool list; approve/reject also refuse agent names as the approver.
HUMAN_ONLY_TOOLS = frozenset({"approve_payment", "reject_payment", "record_human_decision"})
AGENT_NAMES = frozenset({"boss", "inventory", "accounting", "facilities", "customer_service"})

TICKET_STATUSES = ("open", "in_progress", "awaiting_approval", "blocked", "resolved")

mcp = FastMCP(
    "Campus Customs Ops",
    instructions=(
        "Shop tools for the Campus Customs agent team. All dates are relative to "
        "desk.date_today in the database, not the real calendar. Use only what the "
        "tools return; never invent stock, prices, vendors or dates. Payments need "
        "human approval: agents can only create approval requests."
    ),
)


# ---------- Database helpers ----------

# Board tables the team adds to the WORKING COPY only (the original is never touched).
BOARD_SCHEMA = """
CREATE TABLE IF NOT EXISTS approval_requests (
    id INTEGER PRIMARY KEY,
    ticket_id INTEGER,
    kind TEXT NOT NULL,              -- invoice | rent | purchase_order
    ref_id INTEGER NOT NULL,         -- invoice id | lease id | vendor id
    payee TEXT NOT NULL,
    amount REAL NOT NULL,
    details TEXT,                    -- JSON: due date, sku/size/qty, etc.
    requested_by TEXT NOT NULL,      -- agent name
    reason TEXT,
    status TEXT NOT NULL,            -- pending | approved | rejected
    created_at TEXT NOT NULL,
    decided_by TEXT,                 -- the human
    decided_at TEXT,
    decision_note TEXT,
    payment_id INTEGER
);
CREATE TABLE IF NOT EXISTS board_notes (
    id INTEGER PRIMARY KEY,
    ticket_id INTEGER NOT NULL,
    kind TEXT NOT NULL,              -- draft | status | human_decision
    author TEXT NOT NULL,
    recipient TEXT,
    subject TEXT,
    body TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


def _check_path() -> None:
    if DB_PATH.name == ORIGINAL_DB_NAME:
        raise ToolError("Refusing to use the original campus_customs.db. Point CAMPUS_DB_PATH at campus_customs_new.db.")
    if not DB_PATH.exists():
        raise ToolError(f"Database not found at {DB_PATH}. Copy data/campus_customs.db to data/campus_customs_new.db.")


@contextmanager
def _db(write: bool = False) -> Iterator[sqlite3.Connection]:
    """Read tools open the working copy read-only. Write tools get one transaction:
    everything commits together or nothing does."""
    _check_path()
    if write:
        conn = sqlite3.connect(DB_PATH, timeout=10)
        conn.execute("PRAGMA foreign_keys = ON")
    else:
        conn = sqlite3.connect(f"file:{DB_PATH.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        if write:
            conn.execute("BEGIN IMMEDIATE")  # lock now, so two approvals can't race on cash
        yield conn
        if write:
            conn.commit()
    except BaseException:
        if write:
            conn.rollback()
        raise
    finally:
        conn.close()


def _ensure_board_tables() -> None:
    _check_path()
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.executescript(BOARD_SCHEMA)
    finally:
        conn.close()


def _has_table(conn: sqlite3.Connection, name: str) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone() is not None


def _today(conn: sqlite3.Connection) -> date:
    """The shop's 'today' comes from desk.date_today."""
    row = conn.execute("SELECT date_today FROM desk LIMIT 1").fetchone()
    if row is None:
        raise ToolError("desk.date_today is missing, so 'today' is unknown.")
    return date.fromisoformat(row["date_today"])


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _add_month(d: date) -> date:
    year, month = (d.year + 1, 1) if d.month == 12 else (d.year, d.month + 1)
    return date(year, month, min(d.day, calendar.monthrange(year, month)[1]))


def _due_status(today: date, due: str) -> dict:
    days = (date.fromisoformat(due) - today).days
    status = "overdue" if days < 0 else "due today" if days == 0 else "upcoming"
    return {"due_date": due, "days_until_due": days, "due_status": status}


def _cash(conn: sqlite3.Connection, account: str = "checking") -> sqlite3.Row:
    row = conn.execute("SELECT name, balance, date FROM cash_accounts WHERE name = ?", (account,)).fetchone()
    if row is None:
        raise ToolError(f"Cash account '{account}' is not in cash_accounts.")
    return row


def _pending_total(conn: sqlite3.Connection, exclude_id: int | None = None) -> float:
    if not _has_table(conn, "approval_requests"):
        return 0.0
    row = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) AS total FROM approval_requests WHERE status = 'pending' AND id IS NOT ?",
        (exclude_id,),
    ).fetchone()
    return round(row["total"], 2)


def _request_dict(r: sqlite3.Row, conn: sqlite3.Connection | None = None) -> dict:
    d = dict(r)
    d["details"] = json.loads(d["details"]) if d.get("details") else {}
    # An approved purchase order is the order to the vendor (homework model: no real vendor is contacted).
    if conn is not None and d["kind"] == "purchase_order" and d["status"] == "approved" and d.get("payment_id"):
        pay = conn.execute("SELECT paid_at FROM payments WHERE id = ?", (d["payment_id"],)).fetchone()
        lead = d["details"].get("lead_days")
        if pay is not None and lead is not None:
            d["order_status"] = "placed with vendor (approved and paid by a human)"
            d["order_placed_on"] = pay["paid_at"]
            d["expected_arrival"] = date.fromordinal(date.fromisoformat(pay["paid_at"]).toordinal() + int(lead)).isoformat()
    return d


def _ticket_dict(conn: sqlite3.Connection, ticket_id: int) -> dict:
    t = conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
    if t is None:
        raise ToolError(f"Ticket {ticket_id} is not in the tickets table.")
    return dict(t)


# ---------- Tickets ----------

@mcp.tool(annotations=READ_ONLY)
def list_tickets() -> dict:
    """Every ticket (open and resolved) with its current status, for the dashboard
    board. `is_resolved` is true only when status is 'resolved'."""
    with _db() as conn:
        today = _today(conn)
        rows = conn.execute("SELECT * FROM tickets ORDER BY id").fetchall()
        tickets = [{**dict(r), "is_resolved": r["status"] == "resolved", "urgency": _urgency(conn, today, r)} for r in rows]
    return {"date_today": today.isoformat(), "count": len(tickets), "tickets": tickets}


def _urgency(conn: sqlite3.Connection, today: date, t: sqlite3.Row) -> dict | None:
    """A due-date fact for the ticket, taken from its linked invoice or lease (never guessed).
    None when the ticket links to nothing with a due date."""
    if t["invoice_id"] is not None:
        inv = conn.execute("SELECT id, due_date, status FROM invoices WHERE id = ?", (t["invoice_id"],)).fetchone()
        if inv is not None and inv["status"] == "open":
            d = _due_status(today, inv["due_date"])
            return {"source": f"invoice {inv['id']}", **d}
    if t["lease_id"] is not None:
        lease = conn.execute("SELECT id, next_due FROM leases WHERE id = ?", (t["lease_id"],)).fetchone()
        if lease is not None:
            return {"source": f"lease {lease['id']} rent", **_due_status(today, lease["next_due"])}
    return None


@mcp.tool(annotations=READ_ONLY)
def list_open_tickets() -> dict:
    """List every ticket that is not resolved yet (the board), oldest first, with
    desk.date_today."""
    with _db() as conn:
        today = _today(conn)
        rows = conn.execute("SELECT * FROM tickets WHERE status != 'resolved' ORDER BY created_at").fetchall()
    return {"date_today": today.isoformat(), "count": len(rows), "tickets": [dict(r) for r in rows]}


@mcp.tool(annotations=READ_ONLY)
def get_ticket(ticket_id: int) -> dict:
    """One ticket with everything already on the board for it: saved drafts,
    status notes, and payment approval requests (pending, approved or rejected).

    Args:
        ticket_id: The ticket number, e.g. 101.
    """
    with _db() as conn:
        today = _today(conn)
        ticket = _ticket_dict(conn, ticket_id)
        notes, requests = [], []
        if _has_table(conn, "board_notes"):
            notes = [dict(r) for r in conn.execute(
                "SELECT * FROM board_notes WHERE ticket_id = ? ORDER BY id", (ticket_id,))]
        if _has_table(conn, "approval_requests"):
            requests = [_request_dict(r, conn) for r in conn.execute(
                "SELECT * FROM approval_requests WHERE ticket_id = ? ORDER BY id", (ticket_id,))]
    return {"date_today": today.isoformat(), "ticket": ticket, "board_notes": notes, "approval_requests": requests}


@mcp.tool(annotations=WRITES)
def update_ticket_status(
    ticket_id: int,
    status: Literal["open", "in_progress", "awaiting_approval", "blocked", "resolved"],
    note: str,
    author: str,
) -> dict:
    """Set a ticket's status on the board and record why. A ticket cannot be set to
    'resolved' while it still has a pending payment approval request.

    Args:
        ticket_id: The ticket number.
        status: open | in_progress | awaiting_approval | blocked | resolved.
        note: One or two sentences on why (what was verified, what is pending).
        author: Who is setting it (normally "boss").
    """
    if not note.strip():
        raise ToolError("A note explaining the status is required.")
    _ensure_board_tables()
    with _db(write=True) as conn:
        ticket = _ticket_dict(conn, ticket_id)
        if status == "resolved":
            pending = conn.execute(
                "SELECT id FROM approval_requests WHERE ticket_id = ? AND status = 'pending'", (ticket_id,)
            ).fetchall()
            if pending:
                raise ToolError(
                    f"Ticket {ticket_id} still has pending approval request(s) {[r['id'] for r in pending]}; "
                    "it must stay awaiting_approval until a human decides."
                )
        conn.execute("UPDATE tickets SET status = ? WHERE id = ?", (status, ticket_id))
        conn.execute(
            "INSERT INTO board_notes (ticket_id, kind, author, subject, body, created_at) VALUES (?, 'status', ?, ?, ?, ?)",
            (ticket_id, author, f"{ticket['status']} -> {status}", note.strip(), _now()),
        )
    return {"ticket_id": ticket_id, "old_status": ticket["status"], "new_status": status, "note": note.strip()}


@mcp.tool(annotations=WRITES)
def save_draft(ticket_id: int, recipient: str, subject: str, body: str, author: str) -> dict:
    """Save a message DRAFT on the board for a ticket. Nothing is sent: there is no
    email, phone or vendor channel. A human reads the draft on the dashboard.

    Args:
        ticket_id: The ticket the message is about.
        recipient: Who it is addressed to (the ticket requester, as on the ticket).
        subject: Message subject.
        body: Message text (clearly labelled as a draft).
        author: Who wrote it (normally "customer_service").
    """
    if not body.strip():
        raise ToolError("The draft body is empty.")
    _ensure_board_tables()
    with _db(write=True) as conn:
        _ticket_dict(conn, ticket_id)
        cur = conn.execute(
            "INSERT INTO board_notes (ticket_id, kind, author, recipient, subject, body, created_at) "
            "VALUES (?, 'draft', ?, ?, ?, ?, ?)",
            (ticket_id, author, recipient, subject, body, _now()),
        )
    return {"draft_id": cur.lastrowid, "ticket_id": ticket_id, "status": "draft (saved on the board, not sent)"}


# ---------- Stock, vendors, rent ----------

@mcp.tool(annotations=READ_ONLY)
def check_stock_and_price(sku: str, size: str, qty_needed: int = 1) -> dict:
    """Check shelf stock for one SKU and size, the shortfall for a requested
    quantity, and the SKU's unit cost and list price (for margin and discount checks).

    Args:
        sku: Product code, e.g. "CC-HOOD-NAVY".
        size: Size, e.g. "S", "M", "L", "XL", or "OS" for one-size items.
        qty_needed: How many units the ticket asks for.
    """
    if qty_needed < 1:
        raise ToolError("qty_needed must be at least 1.")
    sku, size = sku.strip().upper(), size.strip().upper()
    with _db() as conn:
        row = conn.execute(
            "SELECT i.sku, i.name, i.size, i.qty, i.location, p.unit_cost, p.list_price "
            "FROM inventory i LEFT JOIN pricing p ON p.sku = i.sku "
            "WHERE i.sku = ? AND i.size = ?",
            (sku, size),
        ).fetchone()
        if row is None:
            sizes = [r["size"] for r in conn.execute("SELECT size FROM inventory WHERE sku = ?", (sku,))]
            if not sizes:
                raise ToolError(f"SKU {sku} is not in inventory.")
            raise ToolError(f"SKU {sku} has no size {size}. Sizes on record: {', '.join(sizes)}.")

    shortfall = max(qty_needed - row["qty"], 0)
    result = {
        "sku": row["sku"],
        "name": row["name"],
        "size": row["size"],
        "location": row["location"],
        "qty_on_hand": row["qty"],
        "qty_needed": qty_needed,
        "shortfall": shortfall,
        "can_fill_from_stock": shortfall == 0,
        "unit_cost": row["unit_cost"],
        "list_price": row["list_price"],
    }
    if row["unit_cost"] is not None and row["list_price"] is not None:
        result["margin_per_unit_at_list"] = round(row["list_price"] - row["unit_cost"], 2)
        result["margin_pct_at_list"] = round((row["list_price"] - row["unit_cost"]) / row["list_price"] * 100, 1)
    else:
        result["pricing_note"] = f"No pricing row for {sku}."
    return result


@mcp.tool(annotations=READ_ONLY)
def check_vendor_shipping(vendor_id: int | None = None) -> dict:
    """Show which vendors can ship a restock right now. A vendor with any open
    (unpaid) invoice will NOT ship. For each vendor: specialty, lead days, open
    invoices (with days overdue vs desk.date_today), and, if it can ship, the
    earliest arrival date if ordered today.

    Args:
        vendor_id: One vendor's id, or leave empty to list every vendor.
    """
    with _db() as conn:
        today = _today(conn)
        if vendor_id is None:
            vendors = conn.execute("SELECT * FROM vendors ORDER BY id").fetchall()
        else:
            vendors = conn.execute("SELECT * FROM vendors WHERE id = ?", (vendor_id,)).fetchall()
            if not vendors:
                raise ToolError(f"Vendor {vendor_id} is not in the vendors table.")
        open_invoices = conn.execute(
            "SELECT id, vendor_id, amount, due_date, description FROM invoices "
            "WHERE status = 'open' ORDER BY due_date"
        ).fetchall()

    out = []
    for v in vendors:
        invoices = []
        for inv in open_invoices:
            if inv["vendor_id"] != v["id"]:
                continue
            days_overdue = (today - date.fromisoformat(inv["due_date"])).days
            invoices.append({
                "invoice_id": inv["id"],
                "amount": inv["amount"],
                "due_date": inv["due_date"],
                "days_overdue": max(days_overdue, 0),
                "overdue": days_overdue > 0,
                "description": inv["description"],
            })
        can_ship = not invoices
        out.append({
            "vendor_id": v["id"],
            "name": v["name"],
            "specialty": v["specialty"],
            "lead_days": v["lead_days"],
            "open_invoices": invoices,
            "open_balance": round(sum(i["amount"] for i in invoices), 2),
            "can_ship": can_ship,
            "earliest_arrival_if_ordered_today": (
                date.fromordinal(today.toordinal() + v["lead_days"]).isoformat() if can_ship else None
            ),
            "blocked_reason": None if can_ship else "Vendor will not ship while it has an open unpaid invoice.",
        })
    return {"date_today": today.isoformat(), "vendors": out}


@mcp.tool(annotations=READ_ONLY)
def get_rent_due(lease_id: int) -> dict:
    """Look up a lease's rent: space, landlord, monthly rent, next due date,
    and how many days until it is due (or overdue) vs desk.date_today.

    Args:
        lease_id: The lease id, e.g. from a rent_notice ticket.
    """
    with _db() as conn:
        today = _today(conn)
        lease = conn.execute("SELECT * FROM leases WHERE id = ?", (lease_id,)).fetchone()
        if lease is None:
            raise ToolError(f"Lease {lease_id} is not in the leases table.")
        # Rent already paid on this lease, with the due date each payment covered (from its approved request).
        paid = []
        for p in conn.execute("SELECT * FROM payments WHERE kind = 'rent' AND ref_id = ? ORDER BY id", (lease_id,)):
            covered = None
            if _has_table(conn, "approval_requests"):
                req = conn.execute("SELECT details FROM approval_requests WHERE payment_id = ?", (p["id"],)).fetchone()
                covered = json.loads(req["details"] or "{}").get("rent_for_due_date") if req else None
            paid.append({"payment_id": p["id"], "amount": p["amount"], "paid_at": p["paid_at"],
                         "approved_by": p["approved_by"], "rent_for_due_date": covered})

    days_until_due = (date.fromisoformat(lease["next_due"]) - today).days
    return {
        "rent_payments_recorded": paid,
        "how_next_due_works": "After an approved rent payment, next_due moves forward one month; rent_for_due_date shows which due date each payment covered.",
        "date_today": today.isoformat(),
        "lease_id": lease["id"],
        "space_name": lease["space_name"],
        "landlord": lease["landlord"],
        "monthly_rent": lease["monthly_rent"],
        "next_due": lease["next_due"],
        "days_until_due": days_until_due,
        "overdue": days_until_due < 0,
        "notes": lease["notes"],
    }


# ---------- Cash, invoices, payments ----------

@mcp.tool(annotations=READ_ONLY)
def get_cash_balance(account: str = "checking") -> dict:
    """Cash on hand in a cash account, the total of payment requests still pending
    human approval, and the balance left if all of them were approved. No revenue
    is modelled: this balance only goes down.

    Args:
        account: Cash account name (the shop has "checking").
    """
    with _db() as conn:
        today = _today(conn)
        cash = _cash(conn, account)
        pending = _pending_total(conn)
    return {
        "date_today": today.isoformat(),
        "account": cash["name"],
        "balance": cash["balance"],
        "balance_as_of": cash["date"],
        "pending_approval_total": pending,
        "balance_if_all_pending_approved": round(cash["balance"] - pending, 2),
    }


@mcp.tool(annotations=READ_ONLY)
def get_invoice(invoice_id: int) -> dict:
    """One vendor invoice: vendor, amount, due date and status vs desk.date_today,
    plus any payments already recorded for it and any approval requests for it
    (use this to check for duplicate payments).

    Args:
        invoice_id: The invoice number, e.g. 501.
    """
    with _db() as conn:
        today = _today(conn)
        inv = conn.execute(
            "SELECT i.*, v.name AS vendor_name, v.specialty, v.lead_days FROM invoices i "
            "JOIN vendors v ON v.id = i.vendor_id WHERE i.id = ?", (invoice_id,)
        ).fetchone()
        if inv is None:
            raise ToolError(f"Invoice {invoice_id} is not in the invoices table.")
        payments = [dict(r) for r in conn.execute(
            "SELECT * FROM payments WHERE kind = 'invoice' AND ref_id = ? ORDER BY id", (invoice_id,))]
        requests = []
        if _has_table(conn, "approval_requests"):
            requests = [_request_dict(r, conn) for r in conn.execute(
                "SELECT * FROM approval_requests WHERE kind = 'invoice' AND ref_id = ? ORDER BY id", (invoice_id,))]
    return {
        "date_today": today.isoformat(),
        "invoice_id": inv["id"],
        "vendor_id": inv["vendor_id"],
        "vendor_name": inv["vendor_name"],
        "amount": inv["amount"],
        "status": inv["status"],
        "description": inv["description"],
        **_due_status(today, inv["due_date"]),
        "payments_recorded": payments,
        "approval_requests": requests,
    }


@mcp.tool(annotations=READ_ONLY)
def list_payments(kind: Literal["invoice", "rent", "purchase_order"] | None = None, ref_id: int | None = None) -> dict:
    """Payments already made (each one was approved by a human). Filter by kind and
    reference to check for duplicates or to confirm a payment was recorded.

    Args:
        kind: invoice | rent | purchase_order, or empty for all.
        ref_id: invoice id, lease id, or approval request id (purchase orders).
    """
    sql, args = "SELECT * FROM payments WHERE 1=1", []
    if kind:
        sql += " AND kind = ?"; args.append(kind)
    if ref_id is not None:
        sql += " AND ref_id = ?"; args.append(ref_id)
    with _db() as conn:
        rows = [dict(r) for r in conn.execute(sql + " ORDER BY id", args)]
    return {"count": len(rows), "total": round(sum(r["amount"] for r in rows), 2), "payments": rows}


@mcp.tool(annotations=WRITES)
def request_payment_approval(
    ticket_id: int,
    kind: Literal["invoice", "rent", "purchase_order"],
    ref_id: int,
    requested_by: str,
    reason: str,
    sku: str | None = None,
    size: str | None = None,
    qty: int | None = None,
) -> dict:
    """Ask a HUMAN to approve a payment. This does NOT pay anything: it puts a
    pending approval request on the board. The amount and payee are looked up from
    the database (invoice amount, monthly rent, or qty x unit_cost), never typed in.
    Refused if: the reference doesn't exist, it is already paid or already
    requested (duplicate), the vendor is blocked (purchase orders), or cash minus
    all pending requests minus this one would go below $0.

    Args:
        ticket_id: The ticket this payment belongs to.
        kind: invoice (ref_id = invoice id), rent (ref_id = lease id), or
            purchase_order (ref_id = vendor id, plus sku, size and qty).
        ref_id: See kind.
        requested_by: The agent asking (normally "accounting").
        reason: Why this payment is needed, with the verified facts.
        sku: Purchase orders only: product code.
        size: Purchase orders only: size.
        qty: Purchase orders only: units to order.
    """
    _ensure_board_tables()
    with _db(write=True) as conn:
        today = _today(conn)
        _ticket_dict(conn, ticket_id)
        details: dict = {}

        if kind == "invoice":
            inv = conn.execute(
                "SELECT i.*, v.name AS vendor_name FROM invoices i JOIN vendors v ON v.id = i.vendor_id WHERE i.id = ?",
                (ref_id,)).fetchone()
            if inv is None:
                raise ToolError(f"Invoice {ref_id} is not in the invoices table.")
            if inv["status"] != "open":
                raise ToolError(f"Invoice {ref_id} has status '{inv['status']}', not open. Nothing to pay.")
            if conn.execute("SELECT 1 FROM payments WHERE kind='invoice' AND ref_id=?", (ref_id,)).fetchone():
                raise ToolError(f"Duplicate: a payment for invoice {ref_id} is already recorded.")
            payee, amount = inv["vendor_name"], inv["amount"]
            details = {"vendor_id": inv["vendor_id"], "description": inv["description"], **_due_status(today, inv["due_date"])}
            dup_sql, dup_args = "kind='invoice' AND ref_id=?", (ref_id,)

        elif kind == "rent":
            lease = conn.execute("SELECT * FROM leases WHERE id = ?", (ref_id,)).fetchone()
            if lease is None:
                raise ToolError(f"Lease {ref_id} is not in the leases table.")
            payee, amount = lease["landlord"], lease["monthly_rent"]
            details = {"space_name": lease["space_name"], "rent_for_due_date": lease["next_due"], **_due_status(today, lease["next_due"])}
            dup_sql, dup_args = "kind='rent' AND ref_id=? AND json_extract(details, '$.rent_for_due_date') = ?", (ref_id, lease["next_due"])

        else:  # purchase_order
            if not (sku and size and qty and qty > 0):
                raise ToolError("Purchase orders need sku, size and a positive qty.")
            sku, size = sku.strip().upper(), size.strip().upper()
            vendor = conn.execute("SELECT * FROM vendors WHERE id = ?", (ref_id,)).fetchone()
            if vendor is None:
                raise ToolError(f"Vendor {ref_id} is not in the vendors table.")
            blocking = conn.execute("SELECT id, amount FROM invoices WHERE vendor_id = ? AND status = 'open'", (ref_id,)).fetchall()
            if blocking:
                raise ToolError(
                    f"Vendor {vendor['name']} will not ship while invoice(s) {[b['id'] for b in blocking]} are unpaid. "
                    "Get the invoice paid (with human approval) first."
                )
            if not conn.execute("SELECT 1 FROM inventory WHERE sku = ? AND size = ?", (sku, size)).fetchone():
                raise ToolError(f"{sku} size {size} is not in inventory.")
            price = conn.execute("SELECT unit_cost FROM pricing WHERE sku = ?", (sku,)).fetchone()
            if price is None:
                raise ToolError(f"No unit_cost for {sku} in pricing, so the order can't be costed.")
            payee, amount = vendor["name"], round(qty * price["unit_cost"], 2)
            details = {"sku": sku, "size": size, "qty": qty, "unit_cost": price["unit_cost"],
                       "lead_days": vendor["lead_days"],
                       "arrival_if_paid_today": date.fromordinal(today.toordinal() + vendor["lead_days"]).isoformat()}
            dup_sql, dup_args = ("kind='purchase_order' AND ref_id=? AND json_extract(details,'$.sku')=? "
                                 "AND json_extract(details,'$.size')=? AND ticket_id=?"), (ref_id, sku, size, ticket_id)

        dup = conn.execute(
            f"SELECT id, status FROM approval_requests WHERE {dup_sql} AND status IN ('pending','approved')", dup_args
        ).fetchone()
        if dup:
            raise ToolError(f"Duplicate: approval request {dup['id']} for this already exists (status {dup['status']}).")

        cash = _cash(conn)
        pending = _pending_total(conn)
        projected = round(cash["balance"] - pending - amount, 2)
        if projected < 0:
            raise ToolError(
                f"Refused: cash {cash['balance']:.2f} minus pending requests {pending:.2f} minus this {amount:.2f} "
                f"would leave {projected:.2f}. No negative balances."
            )
        cur = conn.execute(
            "INSERT INTO approval_requests (ticket_id, kind, ref_id, payee, amount, details, requested_by, reason, status, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)",
            (ticket_id, kind, ref_id, payee, amount, json.dumps(details), requested_by, reason, _now()),
        )
    return {
        "approval_request_id": cur.lastrowid,
        "status": "pending (awaiting human approval; nothing has been paid)",
        "ticket_id": ticket_id, "kind": kind, "ref_id": ref_id, "payee": payee, "amount": amount,
        "details": details,
        "cash_balance": cash["balance"],
        "other_pending_total": pending,
        "projected_balance_if_all_approved": projected,
    }


@mcp.tool(annotations=READ_ONLY)
def list_approval_requests(
    status: Literal["pending", "approved", "rejected"] | None = None, ticket_id: int | None = None
) -> dict:
    """Payment approval requests on the board, optionally filtered by status or ticket.

    Args:
        status: pending | approved | rejected, or empty for all.
        ticket_id: Only this ticket's requests.
    """
    with _db() as conn:
        if not _has_table(conn, "approval_requests"):
            return {"count": 0, "requests": []}
        sql, args = "SELECT * FROM approval_requests WHERE 1=1", []
        if status:
            sql += " AND status = ?"; args.append(status)
        if ticket_id is not None:
            sql += " AND ticket_id = ?"; args.append(ticket_id)
        rows = [_request_dict(r, conn) for r in conn.execute(sql + " ORDER BY id", args)]
    return {"count": len(rows), "requests": rows}


# ---------- HUMAN-ONLY: approve / reject (hidden from agents by the backend) ----------

def _check_human(approver: str) -> str:
    name = approver.strip()
    if not name or name.lower() in AGENT_NAMES or "agent" in name.lower():
        raise ToolError("Payments must be approved by a named human, not an agent.")
    return name


@mcp.tool(annotations=HUMAN_ONLY)
def approve_payment(request_id: int, approver: str, account: str = "checking") -> dict:
    """HUMAN ONLY. Approve a pending payment request and pay it. In one transaction:
    re-check that cash covers it (refuse if the balance would go negative), insert
    the payments row (approved_by = the human), lower cash_accounts.balance, and mark
    the invoice paid or move the lease's next_due forward one month.

    Args:
        request_id: The approval request id.
        approver: The human approving it (full name).
        account: Cash account to pay from.
    """
    approver = _check_human(approver)
    _ensure_board_tables()
    with _db(write=True) as conn:
        today = _today(conn)
        req = conn.execute("SELECT * FROM approval_requests WHERE id = ?", (request_id,)).fetchone()
        if req is None:
            raise ToolError(f"Approval request {request_id} does not exist.")
        if req["status"] != "pending":
            raise ToolError(f"Approval request {request_id} is already {req['status']}.")
        cash = _cash(conn, account)
        new_balance = round(cash["balance"] - req["amount"], 2)
        if new_balance < 0:
            raise ToolError(f"Refused: paying {req['amount']:.2f} from {cash['balance']:.2f} would go negative.")

        effect = {}
        if req["kind"] == "invoice":
            inv = conn.execute("SELECT status FROM invoices WHERE id = ?", (req["ref_id"],)).fetchone()
            if inv is None or inv["status"] != "open":
                raise ToolError(f"Invoice {req['ref_id']} is no longer open; not paying twice.")
            conn.execute("UPDATE invoices SET status = 'paid' WHERE id = ?", (req["ref_id"],))
            effect = {"invoice_id": req["ref_id"], "invoice_status": "paid"}
            pay_ref = req["ref_id"]
        elif req["kind"] == "rent":
            lease = conn.execute("SELECT next_due FROM leases WHERE id = ?", (req["ref_id"],)).fetchone()
            details = json.loads(req["details"] or "{}")
            if lease is None or lease["next_due"] != details.get("rent_for_due_date"):
                raise ToolError("The lease's due date changed since this request; this rent may already be paid.")
            next_due = _add_month(date.fromisoformat(lease["next_due"])).isoformat()
            conn.execute("UPDATE leases SET next_due = ? WHERE id = ?", (next_due, req["ref_id"]))
            effect = {"lease_id": req["ref_id"], "paid_due_date": lease["next_due"], "new_next_due": next_due}
            pay_ref = req["ref_id"]
        else:
            if conn.execute("SELECT 1 FROM invoices WHERE vendor_id = ? AND status = 'open'", (req["ref_id"],)).fetchone():
                raise ToolError("Vendor still has an open invoice and will not ship; pay that first.")
            effect = {"purchase_order": json.loads(req["details"] or "{}")}
            pay_ref = req["id"]

        cur = conn.execute(
            "INSERT INTO payments (kind, ref_id, amount, account, paid_at, approved_by) VALUES (?, ?, ?, ?, ?, ?)",
            (req["kind"], pay_ref, req["amount"], account, today.isoformat(), approver),
        )
        conn.execute("UPDATE cash_accounts SET balance = ?, date = ? WHERE name = ?", (new_balance, today.isoformat(), account))
        conn.execute(
            "UPDATE approval_requests SET status='approved', decided_by=?, decided_at=?, payment_id=? WHERE id=?",
            (approver, _now(), cur.lastrowid, request_id),
        )
    return {
        "approval_request_id": request_id, "ticket_id": req["ticket_id"], "status": "approved and paid", "payment_id": cur.lastrowid,
        "kind": req["kind"], "payee": req["payee"], "amount": req["amount"], "approved_by": approver,
        "cash_before": cash["balance"], "cash_after": new_balance, **effect,
    }


@mcp.tool(annotations=HUMAN_ONLY)
def reject_payment(request_id: int, approver: str, reason: str) -> dict:
    """HUMAN ONLY. Reject a pending payment request. No money moves.

    Args:
        request_id: The approval request id.
        approver: The human rejecting it.
        reason: Why.
    """
    approver = _check_human(approver)
    _ensure_board_tables()
    with _db(write=True) as conn:
        req = conn.execute("SELECT status, ticket_id FROM approval_requests WHERE id = ?", (request_id,)).fetchone()
        if req is None:
            raise ToolError(f"Approval request {request_id} does not exist.")
        if req["status"] != "pending":
            raise ToolError(f"Approval request {request_id} is already {req['status']}.")
        conn.execute(
            "UPDATE approval_requests SET status='rejected', decided_by=?, decided_at=?, decision_note=? WHERE id=?",
            (approver, _now(), reason, request_id),
        )
    return {"approval_request_id": request_id, "ticket_id": req["ticket_id"], "status": "rejected", "rejected_by": approver, "reason": reason}



@mcp.tool(annotations=HUMAN_ONLY)
def record_human_decision(ticket_id: int, decided_by: str, decision: str) -> dict:
    """HUMAN ONLY. Put a manager's decision on a ticket's board (e.g. an authorized discount
    or what counts as done). Agents read it through get_ticket. No money moves.

    Args:
        ticket_id: The ticket the decision is for.
        decided_by: The human making the decision (full name).
        decision: The decision, in the manager's words.
    """
    decided_by = _check_human(decided_by)
    if not decision.strip():
        raise ToolError("The decision text is empty.")
    _ensure_board_tables()
    with _db(write=True) as conn:
        _ticket_dict(conn, ticket_id)
        cur = conn.execute(
            "INSERT INTO board_notes (ticket_id, kind, author, subject, body, created_at) VALUES (?, 'human_decision', ?, ?, ?, ?)",
            (ticket_id, decided_by, "Human decision", decision.strip(), _now()),
        )
    return {"note_id": cur.lastrowid, "ticket_id": ticket_id, "decided_by": decided_by, "decision": decision.strip()}

if __name__ == "__main__":
    mcp.run(show_banner=False)
