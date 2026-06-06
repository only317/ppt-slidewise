import { useState, useRef, useEffect } from 'react'
import type { PipelinePhase, OutlineData, ReviewReportData, DoneData, SessionSummary } from '../types/messages'
import { ChatMessage } from './ChatMessage'
import { DesignPreview } from './DesignPreview'
import { OutlineEditor } from './OutlineEditor'
import { ReviewReport } from './ReviewReport'
import { InputArea } from './InputArea'

interface FileTag { name: string }

interface Props {
  phase: PipelinePhase
  connected: boolean
  sessions: SessionSummary[]
  outline: OutlineData | null
  review: ReviewReportData | null
  done: DoneData | null
  errors: string[]
  statusMessages: string[]
  styleTag: string | null
  fileTags: FileTag[]
  onStyleTagChange: (id: string | null) => void
  onRemoveFile: (i: number) => void
  onSend: (text: string) => void
  onFilesAdded: (files: FileList) => void
  onConfirmOutline: (approved: boolean) => void
  onFix: (pages: number[], ignore: number[], feedback?: string) => void
  onSkipReview: () => void
  onDismissError: (index: number) => void
}

const PHASE_CN: Record<string, string> = {
  idle: '空闲', planning: '规划中', generating: '生成中', reviewing: '审查中', done: '已完成',
}

const PHASE_LABELS: Record<string, string> = {
  planning: '正在分析内容，规划大纲…',
  generating: '正在生成幻灯片…',
  reviewing: '正在审查设计质量…',
}

export function ChatPanel({
  phase, connected, sessions, outline, review, done, errors, statusMessages,
  styleTag, fileTags, onStyleTagChange, onRemoveFile,
  onSend, onFilesAdded, onConfirmOutline, onFix, onSkipReview, onDismissError,
}: Props) {
  const showWelcome = phase === 'idle' && !outline
  const [showSessions, setShowSessions] = useState(false)
  const popRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (popRef.current && !popRef.current.contains(e.target as Node)) setShowSessions(false)
    }
    if (showSessions) document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [showSessions])

  const currentId = new URLSearchParams(window.location.search).get('session') || 'new'

  return (
    <div id="chat-panel">
      <div id="chat-header">
        <span className="logo">SlideWise</span>
        <span className="accent-line" />
        <div className="header-actions">
          <button className="btn-new-chat" title="新建对话"
            onClick={() => { window.location.href = '/?session=new' }}>
            + 新建
          </button>
          <div className="session-picker-wrap" ref={popRef}>
            <button className="btn-sessions" title="历史记录"
              onClick={() => setShowSessions(!showSessions)} disabled={sessions.length === 0}>
              &#9776;
            </button>
            {showSessions && sessions.length > 0 && (
              <div className="session-popover">
                <div className="session-pop-title">历史会话</div>
                {sessions.map(s => (
                  <div key={s.session_id}
                    className={`session-item${s.session_id === currentId ? ' active' : ''}`}
                    onClick={() => { window.location.href = `/?session=${s.session_id}` }}>
                    <span className="si-phase">{PHASE_CN[s.phase] || s.phase}</span>
                    <span className="si-info">
                      {s.slides_generated}/{s.slides_total} 页
                      {s.created_at && <span className="si-time">{new Date(s.created_at).toLocaleString('zh-CN')}</span>}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
          <span className="status">
            {connected
              ? <><span className="indicator" /> 就绪</>
              : <span style={{color:'var(--accent-err)'}}>断开</span>
            }
          </span>
        </div>
      </div>

      <div id="chat-messages">
        {showWelcome && (
          <ChatMessage role="system">
            欢迎使用 SlideWise —— 输入 PPT 主题，或拖入 PDF / ZIP 文件，即可自动生成可编辑的演示文稿。
            <br /><span style={{fontSize:11,color:'var(--text-dim)'}}>
              支持：PDF论文 · Markdown大纲 · GitHub链接 · ZIP项目 · 纯文本主题
            </span>
          </ChatMessage>
        )}

        {outline && <DesignPreview outline={outline} />}
        {outline && <OutlineEditor outline={outline} onConfirm={onConfirmOutline} />}
        {review && <ReviewReport report={review} onFix={onFix} onSkip={onSkipReview} />}
        {done && <DoneCard done={done} />}

        {statusMessages.map((msg, i) => (
          <ChatMessage key={`status-${i}`} role="system">
            <span className="status-msg">{msg}</span>
          </ChatMessage>
        ))}

        {phase !== 'idle' && !done && !statusMessages.length && (
          <ChatMessage role="system">
            <span className="status-msg pulse">{PHASE_LABELS[phase] || '处理中…'}</span>
          </ChatMessage>
        )}

        {errors.map((err, i) => (
          <ChatMessage key={i} role="system">
            <span style={{color:'var(--accent-err)'}}>错误：{err}</span>
            <button className="btn btn-ghost" style={{marginLeft:8,fontSize:10,padding:'2px 8px'}}
              onClick={() => onDismissError(i)}>忽略</button>
          </ChatMessage>
        ))}
      </div>

      <InputArea
        onSend={onSend}
        onFilesAdded={onFilesAdded}
        disabled={phase === 'generating' || phase === 'reviewing'}
        styleTag={styleTag}
        onStyleTagChange={onStyleTagChange}
        fileTags={fileTags}
        onRemoveFile={onRemoveFile}
      />
    </div>
  )
}

function DoneCard({ done }: { done: DoneData }) {
  return (
    <div className="outline-card">
      <div className="oc-header">导出完成</div>
      <p style={{fontSize:12,color:'var(--text-muted)',marginBottom:12}}>{done.filename}</p>
      <a href={done.download_url} className="btn-download" download>下载 .pptx</a>
      <div className="gen-by">由 SlideWise 生成 · 所有元素均为原生 PowerPoint 形状，可直接编辑</div>
    </div>
  )
}
