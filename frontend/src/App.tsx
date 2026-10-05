import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { API_BASE, api, money } from './api'
import { CashPanel, type CashChange } from './components/CashPanel'
import { DecisionPanel } from './components/DecisionPanel'
import { DeskQueue, STATUS_LABEL, urgencyText } from './components/DeskQueue'
import { RunSummary } from './components/RunSummary'
import { AgentRoster, Attention, Connection } from './components/Sidebar'
import { TeamFeed } from './components/TeamFeed'
import { bossDecision, deriveAgents, runIds } from './derive'
import type { AgentEvent, ApprovalRequest, Cash, RunInfo, Ticket, TicketDetail } from './types'

interface Toast { id: number; kind: 'ok' | 'err' | 'info'; text: string }

const TYPE_LABEL: Record<string, string> = { customer_order: 'Customer order', rent_notice: 'Rent notice', price_override: 'Price override' }

export default function App() {
  const [tickets, setTickets] = useState<Ticket[]>([])
  const [dateToday, setDateToday] = useState('')
  const [cash, setCash] = useState<Cash | null>(null)
  const [lastChange, setLastChange] = useState<CashChange | null>(null)
  const [requests, setRequests] = useState<ApprovalRequest[]>([])
  // ?ticket=101 opens that ticket directly (handy for links and screenshots).
  const [selectedId, setSelectedId] = useState<number | null>(() => Number(new URLSearchParams(location.search).get('ticket')) || null)
  const [detail, setDetail] = useState<TicketDetail | null>(null)
  const [events, setEvents] = useState<AgentEvent[]>([])
  const [runChoice, setRunChoice] = useState<string>('all')
  const [activeRun, setActiveRun] = useState<RunInfo | null>(null)
  const [approver, setApprover] = useState(() => localStorage.getItem('approver') ?? '')
  const [busyId, setBusyId] = useState<number | null>(null)
  const [online, setOnline] = useState<boolean | null>(null)
  const [toasts, setToasts] = useState<Toast[]>([])
  const cursor = useRef(0)

  const toast = useCallback((kind: Toast['kind'], text: string) => {
    const id = Date.now() + Math.random()
    setToasts(t => [...t, { id, kind, text }])
    setTimeout(() => setToasts(t => t.filter(x => x.id !== id)), 6000)
  }, [])

  useEffect(() => { localStorage.setItem('approver', approver) }, [approver])

  // ---- board data: tickets, cash, approvals (all from the backend) ----
  const refreshBoard = useCallback(async () => {
    try {
      const [t, c, a] = await Promise.all([api.tickets(), api.cash(), api.approvals()])
      setTickets(t.tickets)
      setDateToday(t.date_today)
      setCash(c)
      setRequests(a.requests)
      setOnline(true)
      setSelectedId(id => id ?? t.tickets.find(x => !x.is_resolved)?.id ?? t.tickets[0]?.id ?? null)
    } catch {
      setOnline(false)
    }
  }, [])

  const refreshDetail = useCallback(async (id: number) => {
    try { setDetail(await api.ticket(id)) } catch { /* offline state is shown */ }
  }, [])

  const pullEvents = useCallback(async (id: number) => {
    try {
      const r = await api.events(cursor.current, id)
      cursor.current = r.next_since
      // Merge by audit index, so overlapping polls (or StrictMode's double effect) never duplicate an event.
      if (r.events.length) setEvents(prev => {
        const seen = new Set(prev.map(e => e.index))
        const fresh = r.events.filter(e => !seen.has(e.index))
        return fresh.length ? [...prev, ...fresh] : prev
      })
    } catch { /* next poll retries */ }
  }, [])

  useEffect(() => { refreshBoard(); const t = setInterval(refreshBoard, 4000); return () => clearInterval(t) }, [refreshBoard])

  useEffect(() => {
    if (selectedId == null) return
    cursor.current = 0
    setEvents([])
    setRunChoice('all')
    refreshDetail(selectedId)
    pullEvents(selectedId)
  }, [selectedId, pullEvents, refreshDetail])

  const running = activeRun?.status === 'running'
  useEffect(() => {
    if (selectedId == null) return
    const t = setInterval(() => { pullEvents(selectedId); if (running) refreshDetail(selectedId) }, running ? 1000 : 5000)
    return () => clearInterval(t)
  }, [selectedId, running, pullEvents, refreshDetail])

  // Pick up a run that is already going (e.g. after a page reload).
  useEffect(() => {
    api.runs().then(rs => { const r = rs.find(x => x.status === 'running'); if (r) { setActiveRun(r); setSelectedId(r.ticket_id) } }).catch(() => {})
  }, [])

  // Watch the active run; the ticket's status only changes on the board once the backend says the run finished.
  useEffect(() => {
    if (!activeRun || activeRun.status !== 'running') return
    const t = setInterval(async () => {
      try {
        const r = await api.run(activeRun.run_id)
        if (r.status !== 'running') {
          setActiveRun(r)
          await refreshBoard()
          await refreshDetail(r.ticket_id)
          await pullEvents(r.ticket_id)
          const status = r.result?.decision?.ticket_status
          if (r.status === 'error') toast('err', `Run on #${r.ticket_id} stopped: ${r.error}`)
          else toast(status === 'resolved' ? 'ok' : 'info', `Ticket #${r.ticket_id} — team finished: ${STATUS_LABEL[status ?? ''] ?? status}`)
        }
      } catch { /* retry */ }
    }, 1500)
    return () => clearInterval(t)
  }, [activeRun, refreshBoard, refreshDetail, pullEvents, toast])

  // ---- actions ----
  const startRun = async () => {
    if (selectedId == null) return
    try {
      const r = await api.runTicket(selectedId)
      setActiveRun(r)
      setRunChoice('all')
      toast('info', `Team started on ticket #${selectedId}`)
    } catch (e) { toast('err', (e as Error).message) }
  }

  const approve = async (r: ApprovalRequest) => {
    setBusyId(r.id)
    try {
      const out = await api.approve(r.id, approver.trim()) as { cash_before?: number; cash_after?: number }
      if (out.cash_before != null && out.cash_after != null)
        setLastChange({ before: out.cash_before, amount: r.amount, after: out.cash_after, payee: r.payee })
      toast('ok', `Approved: paid ${r.payee} ${money(r.amount)}. Checking is now ${money(out.cash_after ?? 0)}.`)
      await refreshBoard()
      if (selectedId) { await refreshDetail(selectedId); await pullEvents(selectedId) }
    } catch (e) { toast('err', `Payment not made: ${(e as Error).message}`) } finally { setBusyId(null) }
  }

  const reject = async (r: ApprovalRequest, reason: string) => {
    setBusyId(r.id)
    try {
      await api.reject(r.id, approver.trim(), reason)
      toast('info', `Rejected ${r.payee} ${money(r.amount)} — no money moved`)
      await refreshBoard()
      if (selectedId) await pullEvents(selectedId)
    } catch (e) { toast('err', (e as Error).message) } finally { setBusyId(null) }
  }

  const reset = async () => {
    if (!confirm('Reset the working database to the original values? Payments, drafts and statuses from earlier runs are cleared (the audit trail is kept).')) return
    try {
      const r = await api.reset()
      setLastChange(null)
      toast('ok', `Database reset — checking back to ${money(r.checking_balance)}`)
      await refreshBoard()
      if (selectedId) refreshDetail(selectedId)
    } catch (e) { toast('err', (e as Error).message) }
  }

  // ---- derived view ----
  const ids = useMemo(() => runIds(events), [events])
  // 'all' = every run on this ticket since the last reset (the summary then covers the whole ticket).
  const shownRun = runChoice === 'latest' ? ids[ids.length - 1] : runChoice
  const runEvents = useMemo(
    () => runChoice === 'all' ? events : events.filter(e => e.run_id === shownRun || (e.run_id == null && e.event.startsWith('human'))),
    [events, shownRun, runChoice],
  )
  const states = useMemo(() => deriveAgents(runEvents.filter(e => e.run_id != null)), [runEvents])
  const decision = useMemo(() => bossDecision(runEvents), [runEvents])
  const selected = tickets.find(t => t.id === selectedId) ?? null
  const pending = requests.filter(r => r.status === 'pending')
  const pendingHere = pending.filter(r => r.ticket_id === selectedId)
  const paid = requests.filter(r => r.status === 'approved')
  const drafts = (detail?.board_notes ?? []).filter(n => n.kind === 'draft')
  const runningHere = running && activeRun?.ticket_id === selectedId
  const urg = selected ? urgencyText(selected) : null

  return (
    <div className="app">
      <header className="masthead">
        <div className="brand">
          <svg viewBox="0 0 40 40" width="38" height="38" aria-hidden>
            <path d="M6 4h28v22c0 6-6 9-14 11C12 35 6 32 6 26z" fill="#13294b" stroke="#d4a72c" strokeWidth="2" />
            <text x="20" y="25" textAnchor="middle" fontFamily="Georgia, serif" fontWeight="700" fontSize="15" fill="#f6f1e6">CC</text>
          </svg>
          <div>
            <div className="brand__name">Campus Customs</div>
            <div className="brand__sub">Print-shop operations desk · Chapel Street, New Haven</div>
          </div>
        </div>
        <div className="masthead__facts">
          <div className="fact"><span>Shop date</span><b>{dateToday || '—'}</b></div>
          <div className="fact"><span>Model</span><b>gpt-6-luna</b></div>
          <button className="btn btn--ghost-light btn--small" onClick={reset} disabled={running}>Reset database</button>
        </div>
      </header>

      {online === false && (
        <div className="banner">Can’t reach the backend at {API_BASE}. Start it from <code>backend/</code> with <code>uvicorn main:app --reload --port 8000</code>.</div>
      )}

      <div className="layout">
        <DeskQueue tickets={tickets} selectedId={selectedId} onSelect={setSelectedId} runningTicket={running ? activeRun!.ticket_id : null} />

        <main className="workbench">
          <div className="area-title area-title--bench"><span>Workbench</span></div>
          {selected && (
            <section className="card ticket">
              <div className="ticket__perf" aria-hidden />
              <div className="ticket__main">
                <div className="ticket__eyebrow">
                  Job Nº {selected.id} · {TYPE_LABEL[selected.type] ?? selected.type} · received {new Date(selected.created_at).toLocaleString('en-US', { dateStyle: 'medium', timeStyle: 'short' })}
                </div>
                <h1>{selected.subject}</h1>
                <p className="ticket__note">“{selected.notes}” <span className="muted">— {selected.requester}</span></p>
                <div className="ticket__facts">
                  <span className={`status status--${runningHere ? 'running' : selected.status}`}>
                    {selected.is_resolved && '✓ '}{runningHere ? 'Running' : STATUS_LABEL[selected.status] ?? selected.status}
                  </span>
                  {selected.sku && <span className="fact-chip">{selected.sku} · size {selected.size} · qty {selected.qty}</span>}
                  {selected.invoice_id && <span className="fact-chip">Invoice {selected.invoice_id}</span>}
                  {selected.lease_id && <span className="fact-chip">Lease {selected.lease_id}</span>}
                  {urg && <span className={`fact-chip urgency--${urg.tone}`}>{urg.text}</span>}
                </div>
              </div>
              <div className="ticket__side">
                <button className="btn btn--start" onClick={startRun} disabled={running}>
                  {runningHere ? <><span className="spinner" /> Team working…</> : running ? 'Another ticket is running' : ids.length ? 'Start team again' : 'Start team'}
                </button>
                {ids.length > 0 && (
                  <select className="runpick" value={runChoice} onChange={e => setRunChoice(e.target.value)} aria-label="Show run">
                    <option value="all">All runs on this ticket ({ids.length})</option>
                    <option value="latest">Latest run only</option>
                    {ids.map((id, i) => <option key={id} value={id}>Run {i + 1} · {id}</option>)}
                  </select>
                )}
              </div>
            </section>
          )}

          <DecisionPanel requests={pendingHere} cash={cash} approver={approver} setApprover={setApprover}
            onApprove={approve} onReject={reject} busyId={busyId} />
          <TeamFeed events={runEvents} running={!!runningHere} states={states} />
          <RunSummary states={states} decision={decision} drafts={drafts} />
        </main>

        <aside className="ops">
          <div className="area-title"><span>Operations</span></div>
          <CashPanel cash={cash} paid={paid} lastChange={lastChange} />
          <Attention pending={pending} tickets={tickets} selectedId={selectedId} onOpen={setSelectedId} />
          <AgentRoster states={states} />
          <Connection online={online} apiBase={API_BASE} />
        </aside>
      </div>

      <div className="toasts" aria-live="polite">
        {toasts.map(t => <div key={t.id} className={`toast toast--${t.kind}`}>{t.text}</div>)}
      </div>
    </div>
  )
}
