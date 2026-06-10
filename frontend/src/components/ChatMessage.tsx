import type { ReactNode } from 'react'

interface Props {
  role: 'system' | 'user' | 'assistant'
  agent?: string       // 'strategist' | 'generator' | 'reviewer'
  thinking?: boolean   // true = thinking/tool-call bubble (collapsed)
  children: ReactNode
}

const AGENT_META: Record<string, { label: string; icon: string; color: string }> = {
  strategist: { label: 'Strategist', icon: '\ud83d\udcd6', color: '#4a90d9' },
  generator:  { label: 'Generator',  icon: '\ud83c\udfa8', color: '#8b5cf6' },
  reviewer:   { label: 'Reviewer',   icon: '\ud83d\udd0d', color: '#f59e0b' },
}

export function ChatMessage({ role, agent, thinking, children }: Props) {
  const meta = agent ? AGENT_META[agent] : null

  return (
    <div className={'message' + (thinking ? ' thinking-message' : '')} data-role={role}>
      {meta && (
        <div className="agent-badge" style={{ borderColor: meta.color }}>
          <span className="agent-icon">{meta.icon}</span>
          <span className="agent-name" style={{ color: meta.color }}>{meta.label}</span>
        </div>
      )}
      <div className={'content' + (thinking ? ' thinking-content' : '')}>{children}</div>
    </div>
  )
}
