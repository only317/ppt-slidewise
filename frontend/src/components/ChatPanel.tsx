import type { PipelinePhase, OutlineData, ReviewReportData, DoneData } from '../types/messages'
import { ChatMessage } from './ChatMessage'
import { DesignPreview } from './DesignPreview'
import { OutlineEditor } from './OutlineEditor'
import { ReviewReport } from './ReviewReport'
import { InputArea } from './InputArea'

interface Props {
  phase: PipelinePhase
  connected: boolean
  outline: OutlineData | null
  review: ReviewReportData | null
  done: DoneData | null
  errors: string[]
  onSend: (text: string) => void
  onConfirmOutline: (approved: boolean) => void
  onFix: (pages: number[], ignore: number[], feedback?: string) => void
  onSkipReview: () => void
  onDismissError: (index: number) => void
}

export function ChatPanel({
  phase, connected, outline, review, done, errors,
  onSend, onConfirmOutline, onFix, onSkipReview, onDismissError,
}: Props) {
  return (
    <div id="chat-panel">
      <div id="chat-header">
        <span className="logo">SlideWise</span>
        <span className="accent-line" />
        <span className="status">
          {connected
            ? <><span className="indicator" /> 就绪</>
            : <span style={{color:'var(--accent-err)'}}>断开</span>
          }
        </span>
      </div>

      <div id="chat-messages">
        <ChatMessage role="system">
          欢迎使用 SlideWise —— 输入你想要的 PPT 主题，或拖入 PDF/DOCX 文件，我将为你自动生成可编辑的演示文稿。
        </ChatMessage>

        {outline && <DesignPreview outline={outline} />}
        {outline && <OutlineEditor outline={outline} onConfirm={onConfirmOutline} />}
        {review && <ReviewReport report={review} onFix={onFix} onSkip={onSkipReview} />}
        {done && <DoneCard done={done} />}

        {errors.map((err, i) => (
          <ChatMessage key={i} role="system">
            <span style={{color:'var(--accent-err)'}}>错误：{err}</span>
            <button className="btn btn-ghost" style={{marginLeft:8,fontSize:10,padding:'2px 8px'}}
              onClick={() => onDismissError(i)}>忽略</button>
          </ChatMessage>
        ))}
      </div>

      <InputArea onSend={onSend} disabled={phase === 'generating' || phase === 'reviewing'} />
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
