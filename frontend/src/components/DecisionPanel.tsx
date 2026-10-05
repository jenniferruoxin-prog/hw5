import { useState } from 'react'
import { agentMeta } from '../agents'
import { money } from '../api'
import type { ApprovalRequest, Cash } from '../types'

const KIND: Record<string, string> = { invoice: 'Vendor invoice', rent: 'Rent', purchase_order: 'Purchase order' }

function related(r: ApprovalRequest): string {
  const d = r.details as Record<string, string | number | undefined>
  if (r.kind === 'invoice') return `Invoice ${r.ref_id}${d.description ? ` — ${d.description}` : ''}${d.due_date ? ` · due ${d.due_date} (${d.due_status})` : ''}`
  if (r.kind === 'rent') return `Lease ${r.ref_id}${d.space_name ? ` — ${d.space_name}` : ''}${d.rent_for_due_date ? ` · rent due ${d.rent_for_due_date}` : ''}`
  return `Purchase: ${d.sku} size ${d.size} × ${d.qty} @ ${money(Number(d.unit_cost))}${d.lead_days ? ` · ${d.lead_days}-day lead time` : ''}`
}

/** The amber "Human decision required" panel in the Workbench (design.md §5). */
export function DecisionPanel({ requests, cash, approver, setApprover, onApprove, onReject, busyId }: {
  requests: ApprovalRequest[]
  cash: Cash | null
  approver: string
  setApprover: (s: string) => void
  onApprove: (r: ApprovalRequest) => void
  onReject: (r: ApprovalRequest, reason: string) => void
  busyId: number | null
}) {
  const [confirm, setConfirm] = useState<ApprovalRequest | null>(null)
  const [rejecting, setRejecting] = useState<ApprovalRequest | null>(null)
  const [reason, setReason] = useState('')
  if (!requests.length) return null
  const signed = approver.trim().length >= 2

  return (
    <section className="decision-panel" aria-live="polite">
      <div className="decision-panel__title">
        <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden><path d="M12 3l9 16H3z M12 10v4 M12 17h.01" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" /></svg>
        Human decision required
      </div>
      <label className="signer">
        <span>Approving as</span>
        <input value={approver} onChange={e => setApprover(e.target.value)} placeholder="Your full name" />
      </label>
      {requests.map(r => {
        const after = cash ? Math.round((cash.balance - r.amount) * 100) / 100 : null
        const over = after != null && after < 0
        return (
          <div key={r.id} className="dreq">
            <div className="dreq__grid">
              <div><span>Ticket</span><b>#{r.ticket_id}</b></div>
              <div><span>{KIND[r.kind] ?? r.kind} · payee</span><b>{r.payee}</b></div>
              <div><span>Amount</span><b className="dreq__amount">{money(r.amount)}</b></div>
              <div className="dreq__wide"><span>Related</span>{related(r)}</div>
              <div className="dreq__wide"><span>Reason</span>{r.reason ?? '—'} <em>— requested by {agentMeta(r.requested_by).label}</em></div>
              <div><span>Checking now</span><b>{cash ? money(cash.balance) : '—'}</b></div>
              <div><span>After approval</span><b className={over ? 'neg' : ''}>{after != null ? money(after) : '—'}</b></div>
            </div>
            {over && <div className="dreq__warn">This exceeds available cash. The backend will refuse it — no negative balances.</div>}
            <div className="dreq__actions">
              <button className="btn btn--approve" disabled={!signed || busyId === r.id} onClick={() => setConfirm(r)}>
                {busyId === r.id ? 'Paying…' : 'Approve'}
              </button>
              <button className="btn btn--ghost" disabled={!signed || busyId === r.id} onClick={() => { setRejecting(r); setReason('') }}>Reject</button>
              {!signed && <span className="hint">Type your name to decide.</span>}
            </div>
          </div>
        )
      })}

      {confirm && (
        <div className="modal" onClick={() => setConfirm(null)}>
          <div className="modal__card" onClick={e => e.stopPropagation()}>
            <div className="modal__title">Approve and pay?</div>
            <div className="modal__payee">{confirm.payee}</div>
            <div className="modal__amount">{money(confirm.amount)}</div>
            {cash && (
              <div className="modal__math">
                <span>{money(cash.balance)}</span><span>−</span><span>{money(confirm.amount)}</span><span>=</span>
                <b className={cash.balance - confirm.amount < 0 ? 'neg' : ''}>{money(cash.balance - confirm.amount)}</b>
              </div>
            )}
            <div className="modal__who">Signed by <b>{approver}</b> · saved as payments.approved_by</div>
            <div className="modal__actions">
              <button className="btn btn--ghost" onClick={() => setConfirm(null)}>Cancel</button>
              <button className="btn btn--approve" onClick={() => { onApprove(confirm); setConfirm(null) }}>Approve &amp; pay</button>
            </div>
          </div>
        </div>
      )}
      {rejecting && (
        <div className="modal" onClick={() => setRejecting(null)}>
          <div className="modal__card" onClick={e => e.stopPropagation()}>
            <div className="modal__title">Reject {rejecting.payee} · {money(rejecting.amount)}?</div>
            <textarea value={reason} onChange={e => setReason(e.target.value)} placeholder="Reason (required)" rows={3} />
            <div className="modal__actions">
              <button className="btn btn--ghost" onClick={() => setRejecting(null)}>Cancel</button>
              <button className="btn btn--danger" disabled={reason.trim().length < 2}
                onClick={() => { onReject(rejecting, reason.trim()); setRejecting(null) }}>Reject</button>
            </div>
          </div>
        </div>
      )}
    </section>
  )
}
