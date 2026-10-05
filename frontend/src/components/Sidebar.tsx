import { AGENTS, AgentBadge } from '../agents'
import { money } from '../api'
import type { AgentState } from '../derive'
import type { AgentName, ApprovalRequest, Ticket } from '../types'

const STATUS_TEXT: Record<string, string> = {
  idle: 'Idle', thinking: 'Working', tool: 'Checking data', waiting: 'Delegating', done: 'Completed', error: 'Error',
}

/** Agent roster: who is on the team and what each one is doing right now. */
export function AgentRoster({ states }: { states: Record<AgentName, AgentState> }) {
  return (
    <section className="card roster">
      <div className="area-title"><span>Agent roster</span></div>
      {AGENTS.map(a => {
        const s = states[a.name]
        const working = ['thinking', 'tool', 'waiting'].includes(s.status)
        return (
          <div key={a.name} className={`member member--${s.status}`} style={{ ['--agent' as string]: a.color }}>
            <AgentBadge name={a.name} size={32} working={working} />
            <div className="member__text">
              <div className="member__name">{a.label} <span className="member__role">{a.role}</span></div>
              <div className="member__detail" title={s.detail}>{s.status === 'idle' ? 'Not on this run' : s.detail}</div>
            </div>
            <span className={`member__state state--${s.status}`}>{STATUS_TEXT[s.status]}</span>
          </div>
        )
      })}
    </section>
  )
}

/** Anything that needs a human: pending payment approvals (any ticket) and blocked tickets. */
export function Attention({ pending, tickets, selectedId, onOpen }: {
  pending: ApprovalRequest[]
  tickets: Ticket[]
  selectedId: number | null
  onOpen: (ticketId: number) => void
}) {
  const blocked = tickets.filter(t => t.status === 'blocked')
  const count = pending.length + blocked.length
  return (
    <section className={`card attention${count ? ' attention--on' : ''}`}>
      <div className="area-title"><span>Needs attention</span>{count > 0 && <span className="count">{count}</span>}</div>
      {count === 0 && <div className="empty small">Nothing needs a human right now.</div>}
      {pending.map(r => (
        <button key={r.id} className="attn" onClick={() => r.ticket_id && onOpen(r.ticket_id)}>
          <span className="attn__what">Approve {r.kind.replace('_', ' ')} · {r.payee}</span>
          <span className="attn__meta">#{r.ticket_id} · {money(r.amount)}{r.ticket_id === selectedId ? ' · open in Workbench' : ' · open ticket →'}</span>
        </button>
      ))}
      {blocked.map(t => (
        <button key={t.id} className="attn attn--blocked" onClick={() => onOpen(t.id)}>
          <span className="attn__what">Ticket #{t.id} is blocked</span>
          <span className="attn__meta">{t.subject} · open ticket →</span>
        </button>
      ))}
    </section>
  )
}

export function Connection({ online, apiBase }: { online: boolean | null; apiBase: string }) {
  const state = online === null ? 'wait' : online ? 'on' : 'off'
  return (
    <section className={`card conn conn--${state}`}>
      <span className="conn__dot" />
      <div>
        <div className="conn__label">Backend {online === null ? 'connecting…' : online ? 'connected' : 'offline'}</div>
        <div className="conn__url">{apiBase}</div>
      </div>
    </section>
  )
}
