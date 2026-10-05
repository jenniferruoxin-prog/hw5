// Shapes returned by the FastAPI backend (backend/main.py).

export type AgentName = 'boss' | 'inventory' | 'accounting' | 'facilities' | 'customer_service'

export interface Ticket {
  id: number
  type: string
  requester: string
  subject: string
  sku: string | null
  size: string | null
  qty: number | null
  lease_id: number | null
  invoice_id: number | null
  status: string
  notes: string | null
  created_at: string
  is_resolved: boolean
  board_state: 'open' | 'resolved'
  urgency: { source: string; due_date: string; days_until_due: number; due_status: 'overdue' | 'due today' | 'upcoming' } | null
  running: boolean
}

export interface TicketsResponse {
  date_today: string
  count: number
  tickets: Ticket[]
}

export interface BoardNote {
  id: number
  ticket_id: number
  kind: 'draft' | 'status'
  author: string
  recipient: string | null
  subject: string | null
  body: string
  created_at: string
}

export interface ApprovalRequest {
  id: number
  ticket_id: number | null
  kind: 'invoice' | 'rent' | 'purchase_order'
  ref_id: number
  payee: string
  amount: number
  details: Record<string, unknown>
  requested_by: string
  reason: string | null
  status: 'pending' | 'approved' | 'rejected'
  created_at: string
  decided_by: string | null
  decided_at: string | null
  decision_note: string | null
  payment_id: number | null
}

export interface TicketDetail {
  date_today: string
  ticket: Ticket
  board_notes: BoardNote[]
  approval_requests: ApprovalRequest[]
}

export interface Cash {
  date_today: string
  account: string
  balance: number
  balance_as_of: string
  pending_approval_total: number
  balance_if_all_pending_approved: number
}

export interface ToolCall {
  tool: string
  args: unknown
}

export interface AgentEvent {
  index: number
  time: string
  event: string
  run_id: string | null
  ticket_id: number | null
  agent: AgentName | null
  chain: AgentName[] | null
  depth: number | null
  step: number | null
  said?: string | null
  tool_calls?: ToolCall[]
  tool_results?: { tool: string | null; result: string }[]
  tokens?: { input_tokens: number; output_tokens: number } | null
  output?: Record<string, unknown> | null
  error?: string | null
  from_agent?: AgentName
  to_agent?: AgentName
  question?: string
  outcome?: 'answered' | 'refused' | 'error' | 'reused'
  note?: string | null
  details?: Record<string, unknown>
}

export interface EventsResponse {
  total: number
  next_since: number
  events: AgentEvent[]
}

export interface Action {
  description: string
  owner: string
  status: 'recommended' | 'awaiting_approval' | 'executed' | 'refused' | 'resolved'
  evidence_tool?: string | null
}

export interface BossDecision {
  ticket_id: number
  summary: string
  agents_consulted: AgentName[]
  actions: Action[]
  customer_draft: { to: string; subject: string; body: string } | null
  ticket_status: string
  next_steps: string[]
  limitations: string[]
}

export interface RunInfo {
  run_id: string
  ticket_id: number
  status: 'running' | 'done' | 'error'
  started_at: string
  finished_at: string | null
  error: string | null
  result?: { decision: BossDecision | null; error: string | null } | null
}
