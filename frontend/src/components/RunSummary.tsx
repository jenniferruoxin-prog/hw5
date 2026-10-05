import { AGENTS, AgentBadge } from '../agents'
import { labelOf, type AgentState } from '../derive'
import type { AgentName, BoardNote, BossDecision } from '../types'

const ACTION_LABEL: Record<string, string> = {
  recommended: 'Recommended', awaiting_approval: 'Awaiting approval', executed: 'Executed', refused: 'Refused', resolved: 'Resolved',
}

function Letter({ d, label }: { d: BoardNote; label: string }) {
  return (
    <div className="letter">
      <div className="letter__stamp">{label}</div>
      <div className="letter__to">To: {d.recipient}</div>
      <div className="letter__subject">{d.subject}</div>
      <div className="letter__body">{d.body}</div>
      <div className="letter__by">— {labelOf(d.author)}</div>
    </div>
  )
}

/** Final summary (design.md §6): only agents that took part, the Boss's call, and saved drafts. */
export function RunSummary({ states, decision, drafts }: {
  states: Record<AgentName, AgentState>
  decision: BossDecision | null
  drafts: BoardNote[]
}) {
  const involved = AGENTS.filter(a => states[a.name].runs > 0)
  if (!involved.length && !drafts.length) return null
  return (
    <section className="card summary">
      <div className="area-title"><span>Final summary · what each agent did</span></div>

      {decision && (
        <div className="call">
          <div className="call__head">
            <AgentBadge name="boss" size={30} />
            <b>Boss’s call</b>
            <span className={`status status--${decision.ticket_status}`}>{decision.ticket_status.replace('_', ' ')}</span>
          </div>
          <p className="call__summary">{decision.summary}</p>
          {decision.actions?.length > 0 && (
            <ul className="actions">
              {decision.actions.map((a, i) => (
                <li key={i} className={`action action--${a.status}`}>
                  <span className="action__status">{ACTION_LABEL[a.status] ?? a.status}</span>
                  <span>{a.description}</span>
                  <span className="muted small">· {labelOf(a.owner)}</span>
                </li>
              ))}
            </ul>
          )}
          {decision.next_steps?.length > 0 && <div className="call__next"><b>Next for a human:</b> {decision.next_steps.join(' · ')}</div>}
        </div>
      )}

      <div className="who">
        {involved.map(a => {
          const s = states[a.name]
          const tools = Object.entries(s.tools)
          return (
            <div key={a.name} className="who__card" style={{ ['--agent' as string]: a.color }}>
              <div className="who__head">
                <AgentBadge name={a.name} size={26} />
                <b>{a.label}</b>
                <span className="muted small">{s.steps} step{s.steps === 1 ? '' : 's'}{s.runs > 1 ? ` · briefed ${s.runs}×` : ''}</span>
              </div>
              {(s.askedBy.length > 0 || s.delegatedTo.length > 0) && (
                <div className="who__line">
                  {s.askedBy.length > 0 && <>Asked by {s.askedBy.map(labelOf).join(', ')}. </>}
                  {s.delegatedTo.length > 0 && <>Delegated to {s.delegatedTo.map(labelOf).join(', ')}.</>}
                </div>
              )}
              {tools.length > 0 && <div className="who__tools">{tools.map(([t, n]) => <code key={t} className="tool">{t}{n > 1 ? ` ×${n}` : ''}</code>)}</div>}
              {s.answer && <div className="who__answer">{s.answer}</div>}
            </div>
          )
        })}
      </div>

      {drafts.length > 0 && (
        <div className="drafts">
          <Letter d={drafts[drafts.length - 1]} label="Latest draft · not sent" />
          {drafts.length > 1 && (
            <details className="older">
              <summary>{drafts.length - 1} earlier draft{drafts.length > 2 ? 's' : ''} (superseded)</summary>
              {drafts.slice(0, -1).reverse().map(d => <Letter key={d.id} d={d} label="Earlier draft · not sent" />)}
            </details>
          )}
        </div>
      )}
    </section>
  )
}
