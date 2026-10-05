import type { ApprovalRequest, Cash, EventsResponse, RunInfo, TicketDetail, TicketsResponse } from './types'

// The FastAPI backend (backend/main.py). It allows this page's origin (localhost:5173) via CORS.
export const API_BASE = (import.meta.env.VITE_API_URL as string | undefined) ?? 'http://localhost:8000'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
  })
  const body = await res.json().catch(() => ({}))
  if (!res.ok) {
    const detail = (body as { detail?: unknown }).detail
    throw new Error(typeof detail === 'string' ? detail : `Request failed (${res.status})`)
  }
  return body as T
}

export const api = {
  health: () => request<{ status: string; model: string; runs_in_progress: number }>('/api/health'),
  tickets: () => request<TicketsResponse>('/api/tickets'),
  ticket: (id: number) => request<TicketDetail>(`/api/tickets/${id}`),
  runTicket: (id: number) => request<RunInfo>(`/api/tickets/${id}/run`, { method: 'POST' }),
  run: (runId: string) => request<RunInfo>(`/api/runs/${runId}`),
  runs: () => request<RunInfo[]>('/api/runs'),
  events: (since: number, ticketId?: number) =>
    request<EventsResponse>(`/api/events?since=${since}&limit=1000&since_reset=true${ticketId ? `&ticket_id=${ticketId}` : ''}`),
  approvals: (status?: 'pending' | 'approved' | 'rejected') =>
    request<{ count: number; requests: ApprovalRequest[] }>(`/api/approvals${status ? `?status=${status}` : ''}`),
  approve: (id: number, approver: string) =>
    request<Record<string, unknown>>(`/api/approvals/${id}/approve`, { method: 'POST', body: JSON.stringify({ approver }) }),
  reject: (id: number, approver: string, reason: string) =>
    request<Record<string, unknown>>(`/api/approvals/${id}/reject`, { method: 'POST', body: JSON.stringify({ approver, reason }) }),
  cash: () => request<Cash>('/api/cash'),
  reset: () => request<{ status: string; checking_balance: number }>('/api/reset', { method: 'POST' }),
}

export const money = (n: number) =>
  n.toLocaleString('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: 2 })
