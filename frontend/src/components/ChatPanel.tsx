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

const STYLE_CARDS = [
  { family: 'Dark', styles: [
    { id: 'indigo', name: '靛蓝', hex: '#4a90d9', desc: '科技·AI·组会' },
    { id: 'ink', name: '墨水', hex: '#c9a96e', desc: '通用·正式' },
    { id: 'forest', name: '森林', hex: '#7a9a6e', desc: '自然·跨学科' },
    { id: 'dune', name: '沙丘', hex: '#d4956a', desc: '创意·人文' },
  ]},
  { family: 'Light', styles: [
    { id: 'klein-blue', name: '克莱因蓝', hex: '#002FA7', desc: '学术·纯净' },
    { id: 'lemon', name: '柠檬黄', hex: '#c8a200', desc: '年轻·活力' },
    { id: 'lime', name: '柠绿', hex: '#7a9900', desc: '生态·健康' },
    { id: 'safety-orange', name: '安全橙', hex: '#d45a2e', desc: '新闻·运动' },
  ]},
]

function StyleHint({ onSend }: { onSend: (text: string) => void }) {
  return (
    <div className="style-hint">
      <div className="style-hint-title">可用风格 · 点击快速选择</div>
      {STYLE_CARDS.map(family => (
        <div key={family.family} className="style-family">
          <span className="style-family-label">{family.family === 'Dark' ? '深色系' : '亮色系'}</span>
          <div className="style-chips">
            {family.styles.map(s => (
              <button key={s.id} className="style-chip"
                onClick={() => onSend(`帮我做一个PPT，用${s.name}风格（${s.id}）`)}
                title={`${s.name} — ${s.desc}`}>
                <span className="style-chip-dot" style={{background:s.hex}} />
                <span className="style-chip-name">{s.name}</span>
                <span className="style-chip-desc">{s.desc}</span>
              </button>
            ))}
          </div>
        </div>
      ))}
      <div className="style-hint-tip">也可以在上方输入框直接说出你想要的风格</div>
    </div>
  )
}

export function ChatPanel({
  phase, connected, outline, review, done, errors,
  onSend, onConfirmOutline, onFix, onSkipReview, onDismissError,
}: Props) {
  const showWelcome = phase === 'idle' && !outline

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
          欢迎使用 SlideWise —— 输入你想要的 PPT 主题，或拖入 PDF / Markdown 文件，我将为你自动生成可编辑的演示文稿。
        </ChatMessage>

        {showWelcome && <StyleHint onSend={onSend} />}

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
