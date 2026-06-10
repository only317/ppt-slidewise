import { useState, useRef, useEffect } from 'react'
import type { OutlineData, ReviewReportData, DoneData, SessionSummary, AgentThinkingData, AgentMessageData, PageFixedConfirmData, FixBatchDoneData } from '../types/messages'
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
  | { role: 'assistant'; type: 'agent_thinking'; data: AgentThinkingData }
  | { role: 'assistant'; type: 'agent_message'; data: AgentMessageData }
  | { role: 'assistant'; type: 'page_fixed_confirm'; data: PageFixedConfirmData }
  | { role: 'assistant'; type: 'fix_batch_done'; data: FixBatchDoneData }
  | { role: 'assistant'; type: 'slide_diff'; index: number; oldSvg: string; newSvg: string }
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
  onConfirmPageFix?: (index: number, approved: boolean, feedback?: string) => void
  onUndoFix?: () => void
}

export function ChatPanel({
  chatHistory, sessions, outline, review, done,
  styleTag, fileTags, phase,
  onStyleTagChange, onRemoveFile, onSend, onFilesAdded,
  onConfirmOutline, onFix, onSkipReview,
  onConfirmPageFix, onUndoFix,
}: Props) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [chatHistory.length])

  return (
    <div id="chat-panel">
      <ChatHeader sessions={sessions} />
      <ChatBody chatHistory={chatHistory} outline={outline} review={review} done={done}
        onConfirmOutline={onConfirmOutline} onFix={onFix} onSkipReview={onSkipReview}
        onConfirmPageFix={onConfirmPageFix} onUndoFix={onUndoFix} />
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
          onClick={() => { window.location.href = '/?session=new' }}>+ \u65b0\u5efa</button>
        <div className="session-picker-wrap" ref={popRef}>
          <button className="btn-sessions"
            onClick={() => setShowSessions(!showSessions)} disabled={sessions.length === 0}>&#9776;</button>
          {showSessions && sessions.length > 0 && (
            <div className="session-popover">
              <div className="session-pop-title">\u5386\u53f2\u4f1a\u8bdd</div>
              {sessions.map(s => (
                <div key={s.session_id}
                  className={`session-item${s.session_id === currentId ? ' active' : ''}`}
                  onClick={() => { window.location.href = `/?session=${s.session_id}` }}>
                  <span className="si-phase">{PHASE_CN[s.phase]}</span>
                  <span className="si-info">
                    {s.slides_generated}/{s.slides_total} \u9875
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

const PHASE_CN: Record<string, string> = { idle:'\u7a7a\u95f2', planning:'\u89c4\u5212', generating:'\u751f\u6210', reviewing:'\u5ba1\u67e5', done:'\u5b8c\u6210' }

function ChatBody({ chatHistory, outline, review, done, onConfirmOutline, onFix, onSkipReview, onConfirmPageFix, onUndoFix }: {
  chatHistory: ChatEntry[]
  outline: OutlineData | null
  review: ReviewReportData | null
  done: DoneData | null
  onConfirmOutline: (approved: boolean) => void
  onFix: (pages: number[], ignore: number[], feedback?: string) => void
  onSkipReview: () => void
  onConfirmPageFix?: (index: number, approved: boolean, feedback?: string) => void
  onUndoFix?: () => void
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
              <p>{'\u6b22\u8fce\u4f7f\u7528 SlideWise \u2014\u2014 \u8f93\u5165 PPT \u4e3b\u9898\u3001\u4e0a\u4f20 PDF / ZIP\u3001\u6216\u7c98\u8d34 GitHub \u94fe\u63a5\u3002'}</p>
            </ChatMessage>
          }
          if (entry.type === 'outline') {
            return <ChatMessage key={i} role="assistant" agent="strategist">
              <DesignPreview outline={entry.data} />
              {outline && <OutlineEditor outline={outline} onConfirm={onConfirmOutline} />}
            </ChatMessage>
          }
          if (entry.type === 'review') {
            return <ChatMessage key={i} role="assistant" agent="reviewer">
              <ReviewReport report={entry.data} onFix={onFix} onSkip={onSkipReview} />
            </ChatMessage>
          }
          if (entry.type === 'done') {
            return <ChatMessage key={i} role="assistant">
              <DoneCard done={entry.data} />
            </ChatMessage>
          }
          if (entry.type === 'agent_thinking') {
            const d = entry.data
            return <ChatMessage key={i} role="assistant" agent={d.agent} thinking>
              <div className="thinking-line">
                {d.tool_name ? (
                  <span>{'\u2699\ufe0f '}<strong>{d.tool_name}</strong>{d.text ? ` \u2014 ${d.text}` : ''}</span>
                ) : (
                  <span>{d.text}</span>
                )}
              </div>
            </ChatMessage>
          }
          if (entry.type === 'agent_message') {
            const d = entry.data
            return <ChatMessage key={i} role="assistant" agent={d.agent}>
              <div className="agent-text">{d.text}</div>
            </ChatMessage>
          }
          if (entry.type === 'page_fixed_confirm') {
            return <ChatMessage key={i} role="assistant" agent="reviewer">
              <PageFixConfirm data={entry.data} onConfirm={onConfirmPageFix} />
            </ChatMessage>
          }
          if (entry.type === 'fix_batch_done') {
            return <ChatMessage key={i} role="assistant" agent="reviewer">
              <FixBatchDoneCard data={entry.data} onApprove={onSkipReview} onUndo={onUndoFix} />
            </ChatMessage>
          }
          if (entry.type === 'slide_diff') {
            return <ChatMessage key={i} role="assistant" agent="generator">
              <SlideDiffCard index={entry.index} oldSvg={entry.oldSvg} newSvg={entry.newSvg} />
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
  // Input is disabled only during generating (not reviewing - user should be able to chat)
  const busy = phase === 'generating'
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
      <p style={{fontSize:12,color:'var(--text-muted)',marginBottom:12}}>{done.filename}</p>
      <a href={done.download_url} className="btn-download" download>{'\u4e0b\u8f7d .pptx'}</a>
    </div>
  )
}

function PageFixConfirm({ data, onConfirm }: { data: PageFixedConfirmData; onConfirm?: (index: number, approved: boolean, feedback?: string) => void }) {
  const [feedback, setFeedback] = useState('')
  return (
    <div className="outline-card">
      <div className="oc-header">{'\u7b2c '}{data.index}{' \u9875\u5df2\u4fee\u590d'}</div>
      <p style={{fontSize:12,color:'var(--text-muted)',marginBottom:8}}>{'\u8bf7\u786e\u8ba4\u4fee\u590d\u7ed3\u679c'}</p>
      {feedback === '' && (
        <input className="rpc-feedback" type="text"
          placeholder={'\u4e0d\u6ee1\u610f\u7684\u8bdd\uff0c\u8bf7\u63cf\u8ff0\u4fee\u6539\u610f\u89c1'}
          value={feedback} onChange={e => setFeedback(e.target.value)}
          style={{marginBottom:8}} />
      )}
      <div className="action-row">
        <button className="btn btn-success" onClick={() => onConfirm?.(data.index, true)}>
          {'\u6ee1\u610f\uff0c\u7ee7\u7eed'}
        </button>
        {feedback && (
          <button className="btn btn-warning" onClick={() => { onConfirm?.(data.index, false, feedback); setFeedback('') }}>
            {'\u63d0\u4ea4\u610f\u89c1\u5e76\u91cd\u4fee'}
          </button>
        )}
        <button className="btn btn-ghost" onClick={() => onConfirm?.(data.index, false, '\u653e\u5f03\u8fd9\u9875\u7684\u4fee\u6539')}>
          {'\u653e\u5f03\u66f4\u6539'}
        </button>
      </div>
    </div>
  )
}

function FixBatchDoneCard({ data, onApprove, onUndo }: { data: FixBatchDoneData; onApprove?: () => void; onUndo?: () => void }) {
  return (
    <div className="outline-card">
      <div className="oc-header">{'\u4fee\u590d\u5b8c\u6210'}</div>
      <p style={{fontSize:12,color:'var(--text-muted)',marginBottom:8}}>
        {'\u5df2\u4fee\u590d '}{data.fixed_pages.length}{' \u9875\uff0c\u53f3\u4fa7\u9884\u89c8\u5df2\u66f4\u65b0\u3002'}
        {data.total_issues_remaining > 0 && ` \u5269\u4f59 ${data.total_issues_remaining} \u4e2a\u95ee\u9898\u3002`}
      </p>
      <div className="action-row">
        <button className="btn btn-success" onClick={onApprove}>
          {'\u6ee1\u610f\uff0c\u5bfc\u51fa'}
        </button>
        <button className="btn btn-warning" onClick={onUndo}>
          {'\u653e\u5f03\u66f4\u6539\uff0c\u56de\u9000'}
        </button>
      </div>
    </div>
  )
}


function SlideDiffCard({ index, oldSvg, newSvg }: { index: number; oldSvg: string; newSvg: string }) {
  const [showOld, setShowOld] = useState(false)
  return (
    <div className="outline-card">
      <div className="oc-header">{'\u7b2c ' + index + ' \u9875\u5df2\u4fee\u590d'}</div>
      <div className="diff-toggle">
        <button className={'btn-select' + (!showOld ? ' active' : '')} onClick={() => setShowOld(false)}>
          {'\u65b0\u7248'}
        </button>
        <button className={'btn-select' + (showOld ? ' active' : '')} onClick={() => setShowOld(true)}>
          {'\u65e7\u7248'}
        </button>
      </div>
      <div className="diff-preview" dangerouslySetInnerHTML={{ __html: showOld ? oldSvg : newSvg }} />
    </div>
  )
}
