import { useEffect, useRef, type ReactNode } from 'react'
import { AgentBadge, agentMeta } from '../agents'
import { FINAL_TOOLS, labelOf, short, toolArgs, type AgentState } from '../derive'
import { money } from '../api'
import type { AgentEvent, AgentName } from '../types'

const time = (iso: string) => new Date(iso).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
const isFinal = (t: string) => FINAL_TOOLS.has(t) || t.startsWith('final_result')

type Label = 'Briefed' | 'Delegating' | 'Checking data' | 'Data returned' | 'Note' | 'Recommendation' | 'Completed' | 'Error'

function entry(e: AgentEvent): { label: Label; body: ReactNode } | null {
  switch (e.event) {
    case 'agent_start': {
      const parent = e.chain && e.chain.length > 1 ? e.chain[e.chain.length - 2] : null
      return { label: 'Briefed', body: <span className="entry__muted">{parent ? `Took a question from ${labelOf(parent)}` : 'Picked up the ticket'}</span> }
    }
    case 'model_response': {
      const calls = (e.tool_calls ?? []).filter(c => !isFinal(c.tool))
      const del = calls.filter(c => c.tool === 'delegate_to')
      const tools = calls.filter(c => c.tool !== 'delegate_to')
      if (!e.said && !calls.length) return null
      const label: Label = del.length ? 'Delegating' : tools.length ? 'Checking data' : 'Note'
      return {
        label,
        body: (
          <>
            {e.said && <div className="entry__said">{e.said}</div>}
            {del.map((c, i) => {
              const a = c.args as { agent_name?: string; question?: string }
              return <div key={`d${i}`} className="entry__ask">→ <b>{labelOf(a?.agent_name)}</b>: “{short(a?.question ?? '', 160)}”</div>
            })}
            {tools.length > 0 && (
              <div className="entry__tools">{tools.map((c, i) => <code key={i} className="tool"><b>{c.tool}</b>({toolArgs(c.args)})</code>)}</div>
            )}
          </>
        ),
      }
    }
    case 'model_request': {
      const results = (e.tool_results ?? []).filter(r => r.tool && !isFinal(r.tool) && r.tool !== 'delegate_to')
      if (!results.length) return null
      return {
        label: 'Data returned',
        body: <div className="entry__results">{results.map((r, i) => <div key={i}><span>← {r.tool}</span> {short(r.result, 170)}</div>)}</div>,
      }
    }
    case 'agent_end': {
      const out = (e.output ?? {}) as { answer?: string; summary?: string; recommendation?: string | null; ticket_status?: string }
      const isBoss = e.agent === 'boss' && (e.depth ?? 0) === 0
      if (!isBoss && out.recommendation)
        return { label: 'Recommendation', body: <><div className="entry__said">{out.answer}</div><div className="entry__rec">{out.recommendation}</div></> }
      return {
        label: 'Completed',
        body: <div className="entry__said">{out.summary ?? out.answer}{out.ticket_status && <span className={`status status--${out.ticket_status}`}>{out.ticket_status.replace('_', ' ')}</span>}</div>,
      }
    }
    case 'agent_error':
      return { label: 'Error', body: <div className="entry__error">{e.error}</div> }
  }
  return null
}

function SystemLine({ e }: { e: AgentEvent }) {
  if (e.event === 'ticket_start') return <div className="sysline">Ticket handed to the team · run {e.run_id} · {time(e.time)}</div>
  if (e.event === 'ticket_end') {
    const d = (e.details ?? {}) as { ticket_status?: string; error?: string; usage?: { requests: number; input_tokens: number; output_tokens: number } }
    return (
      <div className={`sysline sysline--end${d.error ? ' sysline--err' : ''}`}>
        Run finished · ticket status <b>{(d.ticket_status ?? '—').replace('_', ' ')}</b>
        {d.usage && <> · {d.usage.requests} model calls · {(d.usage.input_tokens + d.usage.output_tokens).toLocaleString()} tokens</>}
        {d.error && <> · {d.error}</>}
      </div>
    )
  }
  if (e.event === 'human_approval' || e.event === 'human_rejection') {
    const d = (e.details ?? {}) as { approver?: string; result?: { amount?: number; payee?: string } }
    return (
      <div className="sysline sysline--human">
        Human decision · {e.event === 'human_approval' ? 'approved and paid' : 'rejected'} by <b>{d.approver}</b>
        {d.result?.payee && <> · {d.result.payee}</>}{d.result?.amount != null && <> · {money(d.result.amount)}</>} · {time(e.time)}
      </div>
    )
  }
  if (e.event === 'delegation' && e.outcome !== 'answered') {
    return <div className="sysline">Delegation {labelOf(e.from_agent)} → {labelOf(e.to_agent)} {e.outcome}{e.note ? ` · ${short(e.note, 100)}` : ''}</div>
  }
  return null
}

export function TeamFeed({ events, running, states }: { events: AgentEvent[]; running: boolean; states: Record<AgentName, AgentState> }) {
  const end = useRef<HTMLDivElement>(null)
  useEffect(() => { if (running) end.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' }) }, [events.length, running])

  // The newest entry of each agent that is still working gets the pulse; finished agents' entries go quiet.
  const lastIndex: Partial<Record<AgentName, number>> = {}
  for (const e of events) if (e.agent) lastIndex[e.agent] = e.index

  return (
    <section className="card feed">
      <div className="area-title">
        <span>Team Feed</span>
        {running && <span className="live"><i /> live</span>}
      </div>
      <div className="feed__list">
        {events.length === 0 && <div className="empty">No agent activity on this ticket yet. Press <b>Start team</b> to begin.</div>}
        {events.map(e => {
          if (!e.agent) return <SystemLine key={e.index} e={e} />
          const item = entry(e)
          if (!item) return null
          const meta = agentMeta(e.agent)
          const st = states[e.agent]
          const working = ['thinking', 'tool', 'waiting'].includes(st?.status) && lastIndex[e.agent] === e.index
          const quiet = st?.status === 'done' && item.label !== 'Completed' && item.label !== 'Recommendation'
          return (
            <div key={e.index} className={`entry${working ? ' entry--working' : ''}${quiet ? ' entry--quiet' : ''}`} style={{ ['--agent' as string]: meta.color }}>
              <AgentBadge name={e.agent} size={30} working={working} />
              <div className="entry__main">
                <div className="entry__head">
                  <b className="entry__name">{meta.label}</b>
                  <span className="entry__role">{meta.role}</span>
                  <span className={`label label--${item.label.toLowerCase().replace(' ', '-')}`}>{item.label}</span>
                  <span className="entry__time">{time(e.time)}</span>
                </div>
                {(e.depth ?? 0) > 0 && <div className="entry__chain">{(e.chain ?? []).map(labelOf).join(' › ')}</div>}
                {item.body}
              </div>
            </div>
          )
        })}
        <div ref={end} />
      </div>
    </section>
  )
}
