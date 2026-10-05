// Turns the raw audit events from /api/events into what the desk shows:
// each agent's live state, a per-agent summary, and the Boss's final decision.
import type { AgentEvent, AgentName, BossDecision } from './types'

export const FINAL_TOOLS = new Set(['final_result'])
const isFinal = (tool: string) => FINAL_TOOLS.has(tool) || tool.startsWith('final_result')

export type AgentStatus = 'idle' | 'thinking' | 'tool' | 'waiting' | 'done' | 'error'

export interface AgentState {
  status: AgentStatus
  detail: string
  steps: number
  runs: number
  tools: Record<string, number>
  delegatedTo: AgentName[]
  askedBy: AgentName[]
  answer: string | null
  tokens: number
}

const blank = (): AgentState => ({
  status: 'idle', detail: 'Off the clock', steps: 0, runs: 0, tools: {}, delegatedTo: [], askedBy: [], answer: null, tokens: 0,
})

export function runIds(events: AgentEvent[]): string[] {
  const ids: string[] = []
  for (const e of events) if (e.run_id && !ids.includes(e.run_id)) ids.push(e.run_id)
  return ids
}

export const short = (v: unknown, n = 90): string => {
  const s = typeof v === 'string' ? v : JSON.stringify(v)
  return s.length > n ? `${s.slice(0, n - 1)}…` : s
}

const argText = (args: unknown) => {
  if (!args || typeof args !== 'object') return ''
  return Object.entries(args as Record<string, unknown>)
    .filter(([k]) => !['reason', 'body', 'context', 'note'].includes(k))
    .map(([k, v]) => `${k}=${short(v, 24)}`)
    .join(', ')
}

export function deriveAgents(events: AgentEvent[]): Record<AgentName, AgentState> {
  const s: Record<AgentName, AgentState> = {
    boss: blank(), inventory: blank(), accounting: blank(), facilities: blank(), customer_service: blank(),
  }
  for (const e of events) {
    const a = e.agent && s[e.agent]
    if (e.event === 'delegation' && e.from_agent && e.to_agent) {
      const from = s[e.from_agent]
      if (from && !from.delegatedTo.includes(e.to_agent)) from.delegatedTo.push(e.to_agent)
      continue
    }
    if (!a || !e.agent) continue
    switch (e.event) {
      case 'agent_start': {
        a.runs += 1
        a.status = 'thinking'
        const parent = e.chain && e.chain.length > 1 ? e.chain[e.chain.length - 2] : null
        if (parent && !a.askedBy.includes(parent)) a.askedBy.push(parent)
        a.detail = parent ? `Picked up a question from ${labelOf(parent)}` : 'Reading the ticket'
        break
      }
      case 'model_response': {
        a.steps += 1
        a.tokens += (e.tokens?.input_tokens ?? 0) + (e.tokens?.output_tokens ?? 0)
        const calls = e.tool_calls ?? []
        for (const c of calls) if (!isFinal(c.tool) && c.tool !== 'delegate_to') a.tools[c.tool] = (a.tools[c.tool] ?? 0) + 1
        const del = calls.find(c => c.tool === 'delegate_to')
        const tool = calls.find(c => !isFinal(c.tool) && c.tool !== 'delegate_to')
        if (del) {
          const to = (del.args as { agent_name?: string })?.agent_name
          a.status = 'waiting'
          a.detail = `Waiting on ${labelOf(to)}`
        } else if (tool) {
          a.status = 'tool'
          a.detail = `${tool.tool}(${argText(tool.args)})`
        } else if (calls.some(c => isFinal(c.tool))) {
          a.status = 'thinking'
          a.detail = 'Filing the report'
        } else if (e.said) {
          a.status = 'thinking'
          a.detail = short(e.said, 70)
        }
        break
      }
      case 'model_request':
        if (a.status !== 'done') { a.status = 'thinking'; a.detail = 'Reading tool results' }
        break
      case 'agent_end': {
        a.status = 'done'
        const out = (e.output ?? {}) as { answer?: string; summary?: string }
        a.answer = out.summary ?? out.answer ?? null
        a.detail = 'Report filed'
        break
      }
      case 'agent_error':
        a.status = 'error'
        a.detail = short(e.error ?? 'Error', 80)
        break
    }
  }
  return s
}

export function bossDecision(events: AgentEvent[]): BossDecision | null {
  for (let i = events.length - 1; i >= 0; i--) {
    const e = events[i]
    if (e.event === 'agent_end' && e.agent === 'boss' && (e.depth ?? 0) === 0 && e.output) return e.output as unknown as BossDecision
  }
  return null
}

export function ticketEnd(events: AgentEvent[]): AgentEvent | null {
  for (let i = events.length - 1; i >= 0; i--) if (events[i].event === 'ticket_end') return events[i]
  return null
}

export function labelOf(name: string | null | undefined): string {
  return ({ boss: 'Boss', inventory: 'Inventory', accounting: 'Accounting', facilities: 'Facilities', customer_service: 'Customer Service' } as Record<string, string>)[name ?? ''] ?? (name ?? 'someone')
}

export function toolArgs(args: unknown): string {
  return argText(args)
}
