import { useEffect, useRef, useState } from 'react'
import type { Ticket } from '../types'

const TYPE_LABEL: Record<string, string> = {
  customer_order: 'Customer order',
  rent_notice: 'Rent notice',
  price_override: 'Price override',
}

export const STATUS_LABEL: Record<string, string> = {
  open: 'Open',
  in_progress: 'In progress',
  awaiting_approval: 'Awaiting approval',
  blocked: 'Blocked',
  resolved: 'Resolved',
}

/** Urgency comes from the ticket's linked invoice or lease due date (the database has no priority field). */
export function urgencyText(t: Ticket): { text: string; tone: 'hot' | 'warm' | 'calm' } {
  const u = t.urgency
  if (!u) return { text: 'No due date on record', tone: 'calm' }
  const d = Math.abs(u.days_until_due)
  if (u.due_status === 'overdue') return { text: `${u.source} · ${d} day${d === 1 ? '' : 's'} overdue`, tone: 'hot' }
  if (u.due_status === 'due today') return { text: `${u.source} · due today`, tone: 'hot' }
  return { text: `${u.source} · due in ${d} day${d === 1 ? '' : 's'}`, tone: d <= 3 ? 'warm' : 'calm' }
}

function TypeIcon({ type }: { type: string }) {
  const p = { fill: 'none', stroke: 'currentColor', strokeWidth: 1.7, strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const }
  if (type === 'customer_order')
    return <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden><path {...p} d="M8 4l-4 3 2 3 2-1v11h8V9l2 1 2-3-4-3-2 1.5h-4z" /></svg>
  if (type === 'rent_notice')
    return <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden><path {...p} d="M4 10l8-6 8 6M6 9v11h12V9M10 20v-6h4v6" /></svg>
  return <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden><path {...p} d="M3 12l9-9h7v7l-9 9zM15.5 7.5h.01" /></svg>
}

function Slip({ t, selected, running, changed, onSelect }: {
  t: Ticket; selected: boolean; running: boolean; changed: boolean; onSelect: () => void
}) {
  const state = running ? 'running' : t.status
  const urg = urgencyText(t)
  return (
    <button className={`slip slip--${state}${selected ? ' slip--selected' : ''}${changed ? ' slip--changed' : ''}`} onClick={onSelect}>
      <div className="slip__head">
        <span className="slip__job">JOB Nº {t.id}</span>
        <span className={`status status--${state}`}>
          {t.is_resolved && <span aria-hidden>✓ </span>}
          {running ? 'Running' : STATUS_LABEL[t.status] ?? t.status}
        </span>
      </div>
      <div className="slip__title"><TypeIcon type={t.type} /> {t.subject}</div>
      <div className="slip__preview">{t.notes}</div>
      <div className="slip__foot">
        <span>{TYPE_LABEL[t.type] ?? t.type} · {t.requester}</span>
      </div>
      <div className={`slip__urgency urgency--${urg.tone}`}>{urg.text}</div>
      {running && <div className="slip__progress" />}
    </button>
  )
}

export function DeskQueue({ tickets, selectedId, onSelect, runningTicket }: {
  tickets: Ticket[]
  selectedId: number | null
  onSelect: (id: number) => void
  runningTicket: number | null
}) {
  // Briefly animate a slip whose status just changed (design.md §8).
  const prev = useRef<Record<number, string>>({})
  const [changed, setChanged] = useState<number[]>([])
  useEffect(() => {
    const ids = tickets.filter(t => prev.current[t.id] && prev.current[t.id] !== t.status).map(t => t.id)
    tickets.forEach(t => { prev.current[t.id] = t.status })
    if (!ids.length) return
    setChanged(ids)
    const timer = setTimeout(() => setChanged([]), 1600)
    return () => clearTimeout(timer)
  }, [tickets])

  const open = tickets.filter(t => !t.is_resolved)
  const resolved = tickets.filter(t => t.is_resolved)
  const slip = (t: Ticket) => (
    <Slip key={t.id} t={t} selected={selectedId === t.id} running={runningTicket === t.id || t.running}
      changed={changed.includes(t.id)} onSelect={() => onSelect(t.id)} />
  )
  return (
    <aside className="queue">
      <div className="area-title"><span>Desk Queue</span><span className="area-title__meta">{open.length} open</span></div>
      <div className="queue__group">{open.length ? open.map(slip) : <div className="empty">All caught up.</div>}</div>
      <div className="area-title area-title--sub"><span>✓ Resolved</span><span className="area-title__meta">{resolved.length}</span></div>
      <div className="queue__group">{resolved.length ? resolved.map(slip) : <div className="empty small">Resolved tickets move here and stay open for review.</div>}</div>
    </aside>
  )
}
