import type { ReactNode } from 'react'

interface Props {
  role: 'system' | 'user' | 'assistant'
  children: ReactNode
}

export function ChatMessage({ role, children }: Props) {
  return (
    <div className="message" data-role={role}>
      <div className="content">{children}</div>
    </div>
  )
}
