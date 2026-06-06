import { useState, useRef, useEffect } from 'react'
import type { OutlineData, ReviewReportData, DoneData, SessionSummary } from '../types/messages'
import { ChatMessage } from './ChatMessage'
import { DesignPreview } from './DesignPreview'
import { OutlineEditor } from './OutlineEditor'
import { ReviewReport } from './ReviewReport'
import { InputArea } from './InputArea'

// ---- Chat history types ----
export type ChatEntry =
  | { role: 'user'; text: string }
  | { role: 'assistant'; type: 'welcome' }
  | { role: 'assistant'; type: 'outline'; data: OutlineData }
  | { role: 'assistant'; type: 'review'; data: ReviewReportData }
  | { role: 'assistant'; type: 'done'; data: DoneData }
  | { role: 'system'; type: 'status'; text: string }
  | { role: 'system'; type: 'error'; text: string }

interface FileTag { name: string }

interface Props {
  chatHistory: ChatEntry[]
  sessions: SessionSummary[]
  outline: OutlineData | null
  review: ReviewReportData | null
  done: DoneData | null
  styleTag: string | null
  fileTags: FileTag[]
  phase: string
  onStyleTagChange: (id: string | null) => void
  onRemoveFile: (i: number) => void
  onSend: (text: string) => void
  onFilesAdded: (files: FileList) => void
  onConfirmOutline: (approved: boolean) => void
  onFix: (pages: number[], ignore: number[], feedback?: string) => void
  onSkipReview: () => void
}

export function ChatPanel({
  chatHistory, sessions, outline, review, done,
  styleTag, fileTags, phase,
  onStyleTagChange, onRemoveFile, onSend, onFilesAdded,
  onConfirmOutline, onFix, onSkipReview,
}: Props) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [chatHistory.length])

  return (
    <div id="chat-panel">
      <ChatHeader sessions={sessions} />
      <ChatBody chatHistory={chatHistory} outline={outline} review={review} done={done}
        onConfirmOutline={onConfirmOutline} onFix={onFix} onSkipReview={onSkipReview} />
      <ChatFooter styleTag={styleTag} fileTags={fileTags} phase={phase}
        onStyleTagChange={onStyleTagChange} onRemoveFile={onRemoveFile}
        onSend={onSend} onFilesAdded={onFilesAdded} />
      <div ref={bottomRef} />
    </div>
  )
}

// ---- Sub-components ----

function ChatHeader({ sessions }: { sessions: SessionSummary[] }) {
  const [showSessions, setShowSessions] = useState(false)
  const popRef = useRef<HTMLDivElement>(null)
  const currentId = new URLSearchParams(window.location.search).get('session') || 'new'

  useEffect(() => {
    const h = (e: MouseEvent) => {
      if (popRef.current && !popRef.current.contains(e.target as Node)) setShowSessions(false)
    }
    if (showSessions) document.addEventListener('mousedown', h)
    return () => document.removeEventListener('mousedown', h)
  }, [showSessions])

  return (
    <div id="chat-header">
      <span className="logo">SlideWise</span>
      <div className="header-actions">
        <button className="btn-new-chat"
          onClick={() => { window.location.href = '/?session=new' }}>+ 新建</button>
        <div className="session-picker-wrap" ref={popRef}>
          <button className="btn-sessions"
            onClick={() => setShowSessions(!showSessions)} disabled={sessions.length === 0}>&#9776;</button>
          {showSessions && sessions.length > 0 && (
            <div className="session-popover">
              <div className="session-pop-title">历史会话</div>
              {sessions.map(s => (
                <div key={s.session_id}
                  className={`session-item${s.session_id === currentId ? ' active' : ''}`}
                  onClick={() => { window.location.href = `/?session=${s.session_id}` }}>
                  <span className="si-phase">{PHASE_CN[s.phase]}</span>
                  <span className="si-info">
                    {s.slides_generated}/{s.slides_total} 页
                    {s.created_at && <span className="si-time">{new Date(s.created_at).toLocaleString('zh-CN')}</span>}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

const PHASE_CN: Record<string, string> = { idle:'空闲', planning:'规划', generating:'生成', reviewing:'审查', done:'完成' }

function ChatBody({ chatHistory, outline, review, done, onConfirmOutline, onFix, onSkipReview }: {
  chatHistory: ChatEntry[]
  outline: OutlineData | null
  review: ReviewReportData | null
  done: DoneData | null
  onConfirmOutline: (approved: boolean) => void
  onFix: (pages: number[], ignore: number[], feedback?: string) => void
  onSkipReview: () => void
}) {
  return (
    <div id="chat-messages">
      {chatHistory.map((entry, i) => {
        if (entry.role === 'user') {
          return <ChatMessage key={i} role="user">{entry.text}</ChatMessage>
        }
        if (entry.role === 'assistant') {
          if (entry.type === 'welcome') {
            return <ChatMessage key={i} role="assistant">
              <p>欢迎使用 SlideWise —— 输入 PPT 主题、上传 PDF / ZIP、或粘贴 GitHub 链接。</p>
            </ChatMessage>
          }
          if (entry.type === 'outline') {
            return <ChatMessage key={i} role="assistant">
              <DesignPreview outline={entry.data} />
              {outline && <OutlineEditor outline={outline} onConfirm={onConfirmOutline} />}
            </ChatMessage>
          }
          if (entry.type === 'review') {
            return <ChatMessage key={i} role="assistant">
              <ReviewReport report={entry.data} onFix={onFix} onSkip={onSkipReview} />
            </ChatMessage>
          }
          if (entry.type === 'done') {
            return <ChatMessage key={i} role="assistant">
              <DoneCard done={entry.data} />
            </ChatMessage>
          }
        }
        if (entry.role === 'system') {
          if (entry.type === 'status') {
            return <ChatMessage key={i} role="system">{entry.text}</ChatMessage>
          }
          if (entry.type === 'error') {
            return <ChatMessage key={i} role="system">
              <span style={{color:'var(--accent-err)'}}>{entry.text}</span>
            </ChatMessage>
          }
        }
        return null
      })}
    </div>
  )
}

function ChatFooter({ styleTag, fileTags, phase, onStyleTagChange, onRemoveFile, onSend, onFilesAdded }: {
  styleTag: string | null
  fileTags: FileTag[]
  phase: string
  onStyleTagChange: (id: string | null) => void
  onRemoveFile: (i: number) => void
  onSend: (text: string) => void
  onFilesAdded: (files: FileList) => void
}) {
  const busy = phase === 'generating' || phase === 'reviewing'
  return (
    <InputArea
      onSend={onSend}
      onFilesAdded={onFilesAdded}
      disabled={busy}
      styleTag={styleTag}
      onStyleTagChange={onStyleTagChange}
      fileTags={fileTags}
      onRemoveFile={onRemoveFile}
    />
  )
}

function DoneCard({ done }: { done: DoneData }) {
  return (
    <div className="outline-card">
      <div className="oc-header">导出完成</div>
      <p style={{fontSize:12,color:'var(--text-muted)',marginBottom:12}}>{done.filename}</p>
      <a href={done.download_url} className="btn-download" download>下载 .pptx</a>
      <div className="gen-by">所有元素均为原生 PowerPoint 形状，可直接编辑</div>
    </div>
  )
}
