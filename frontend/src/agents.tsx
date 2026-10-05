import type { AgentName } from './types'

// Each agent keeps one identity everywhere (design.md §4): colour + icon + role label,
// so colour is never the only thing that tells agents apart.
export interface AgentMeta {
  name: AgentName
  label: string
  role: string
  color: string
  icon: 'compass' | 'box' | 'calculator' | 'building' | 'chat'
}

export const AGENTS: AgentMeta[] = [
  { name: 'boss', label: 'Boss', role: 'Routes tickets · final call', color: '#1e3a6e', icon: 'compass' },
  { name: 'inventory', label: 'Inventory', role: 'Stock, shortfalls, vendors', color: '#2563eb', icon: 'box' },
  { name: 'accounting', label: 'Accounting', role: 'Cash, invoices, margins', color: '#2f7d4f', icon: 'calculator' },
  { name: 'facilities', label: 'Facilities', role: 'Lease & rent', color: '#c2581b', icon: 'building' },
  { name: 'customer_service', label: 'Customer Service', role: 'Drafts — never sends', color: '#7c3aed', icon: 'chat' },
]

export const AGENT: Record<AgentName, AgentMeta> = Object.fromEntries(AGENTS.map(a => [a.name, a])) as Record<AgentName, AgentMeta>

export function agentMeta(name: string | null | undefined): AgentMeta {
  return (name && AGENT[name as AgentName]) || { name: 'boss', label: name ?? 'System', role: '', color: '#64748b', icon: 'compass' }
}

export function AgentIcon({ icon, size = 18, color = 'currentColor' }: { icon: AgentMeta['icon']; size?: number; color?: string }) {
  const p = { fill: 'none', stroke: color, strokeWidth: 1.8, strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const }
  const paths = {
    compass: <><circle {...p} cx="12" cy="12" r="9" /><path {...p} d="M15.5 8.5l-2 5-5 2 2-5z" fill={color} fillOpacity=".2" /></>,
    box: <><path {...p} d="M12 3l8 4.5v9L12 21l-8-4.5v-9z" /><path {...p} d="M4 7.5l8 4.5 8-4.5M12 12v9" /></>,
    calculator: <><rect {...p} x="5" y="3" width="14" height="18" rx="2" /><rect {...p} x="8" y="6" width="8" height="3.5" rx=".5" /><path {...p} d="M8.5 13h.01M12 13h.01M15.5 13h.01M8.5 16.5h.01M12 16.5h.01M15.5 16.5h.01" strokeWidth="2.6" /></>,
    building: <><path {...p} d="M4 21V9l8-5 8 5v12" /><path {...p} d="M9 21v-6h6v6M8 11h.01M12 11h.01M16 11h.01" /></>,
    chat: <><path {...p} d="M4 5h16v11H9l-5 4z" /><path {...p} d="M8 9.5h8M8 12.5h5" /></>,
  }
  return <svg viewBox="0 0 24 24" width={size} height={size} aria-hidden>{paths[icon]}</svg>
}

/** Round badge with the agent's icon (used in the roster, feed and summaries). */
export function AgentBadge({ name, size = 34, working = false }: { name: AgentName; size?: number; working?: boolean }) {
  const a = AGENT[name]
  return (
    <span className={`abadge${working ? ' abadge--working' : ''}`} style={{ ['--agent' as string]: a.color, width: size, height: size }}
      role="img" aria-label={a.label}>
      <AgentIcon icon={a.icon} size={Math.round(size * 0.56)} />
    </span>
  )
}
