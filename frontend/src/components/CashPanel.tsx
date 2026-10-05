import { useEffect, useRef, useState } from 'react'
import { money } from '../api'
import type { ApprovalRequest, Cash } from '../types'

export interface CashChange { before: number; amount: number; after: number; payee: string }

/** Counts from the old balance to the new one, so a payment visibly drains the account. */
function useCountTo(target: number | null) {
  const [value, setValue] = useState(target ?? 0)
  const current = useRef<number | null>(null) // the value on screen right now (survives StrictMode's double effect)
  useEffect(() => {
    if (target == null) return
    if (current.current == null) { current.current = target; setValue(target); return } // first load: no animation
    const start = current.current, delta = target - start
    if (!delta) return
    const reduce = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
    const dur = reduce ? 0 : 1200
    const t0 = performance.now()
    let raf = 0
    const tick = (now: number) => {
      const p = dur ? Math.min(1, (now - t0) / dur) : 1, eased = 1 - Math.pow(1 - p, 3)
      current.current = start + delta * eased
      setValue(current.current)
      if (p < 1) raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    // Background tabs pause animation frames; make sure we still land on the real balance.
    const done = setTimeout(() => { current.current = target; setValue(target) }, dur + 150)
    return () => { cancelAnimationFrame(raf); clearTimeout(done) }
  }, [target])
  return value
}

/** Checking balance card (design.md §7). The balance always comes from the backend. */
export function CashPanel({ cash, paid, lastChange }: { cash: Cash | null; paid: ApprovalRequest[]; lastChange: CashChange | null }) {
  const shown = useCountTo(cash?.balance ?? null)
  const [highlight, setHighlight] = useState(false)
  const prev = useRef<number | null>(null)
  const current = cash?.balance
  useEffect(() => {
    if (current == null) return
    const before = prev.current
    prev.current = current
    if (before == null || before === current) return
    setHighlight(true)
    const t = setTimeout(() => setHighlight(false), 4000)
    return () => clearTimeout(t)
  }, [current])

  const pending = cash?.pending_approval_total ?? 0
  return (
    <section className={`card cashcard${highlight ? ' cashcard--hl' : ''}`}>
      <div className="area-title"><span>Checking balance</span><span className="area-title__meta">as of {cash?.balance_as_of ?? '—'}</span></div>
      <div className="cashcard__big">{cash ? money(shown) : '—'}</div>
      {lastChange && (
        <div className="cashcard__change">
          <div><span>Previous</span><b>{money(lastChange.before)}</b></div>
          <div><span>Paid · {lastChange.payee}</span><b className="neg">−{money(lastChange.amount)}</b></div>
          <div className="cashcard__now"><span>Now</span><b>{money(lastChange.after)}</b></div>
        </div>
      )}
      <div className="cashcard__rows">
        <div><span>Pending approval</span><b>{money(pending)}</b></div>
        <div><span>If all approved</span><b className={(cash?.balance_if_all_pending_approved ?? 0) < 0 ? 'neg' : ''}>{cash ? money(cash.balance_if_all_pending_approved) : '—'}</b></div>
      </div>
      {paid.length > 0 && (
        <div className="ledger">
          <div className="ledger__title">Paid · human approved</div>
          {paid.map(p => (
            <div key={p.id} className="ledger__row">
              <span>{p.payee}<small>{p.kind.replace('_', ' ')} · #{p.ticket_id} · {p.decided_by}</small></span>
              <b>−{money(p.amount)}</b>
            </div>
          ))}
        </div>
      )}
      <div className="cashcard__note">Cash only goes out — no revenue is modelled.</div>
    </section>
  )
}
