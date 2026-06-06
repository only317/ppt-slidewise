import { useState, useRef, useEffect } from 'react'

interface FileTag { name: string }

interface StyleItem { id: string; name: string; hex: string; desc: string; family: 'A' | 'B' }

const STYLES: { family: string; label: string; desc: string; items: StyleItem[] }[] = [
  { family: 'A', label: '电子杂志 × 电子墨水', desc: '暗底、衬线标题、叙事节奏 —— 适合观点分享、个人表达',
    items: [
      { id: 'ink', name: '墨水', hex: '#c9a96e', desc: '深邃·权威·叙事', family: 'A' },
      { id: 'indigo', name: '靛蓝瓷', hex: '#4a90d9', desc: '科技·AI·研究', family: 'A' },
      { id: 'forest', name: '森林墨', hex: '#7a9a6e', desc: '自然·文化·跨学科', family: 'A' },
      { id: 'dune', name: '沙丘', hex: '#d4956a', desc: '怀旧·人文·创意', family: 'A' },
    ]},
  { family: 'B', label: '瑞士国际主义', desc: '白底、单一锚点色、网格至上、极简直角 —— 适合产品分析、方法论',
    items: [
      { id: 'klein-blue', name: '克莱因蓝', hex: '#002FA7', desc: '学术·纯净·产品', family: 'B' },
      { id: 'lemon', name: '柠檬黄', hex: '#FFD500', desc: '年轻·零售·Y2K', family: 'B' },
      { id: 'lime', name: '柠绿', hex: '#C5E803', desc: '生态·健康·Z世代', family: 'B' },
      { id: 'safety-orange', name: '安全橙', hex: '#FF6B35', desc: '新闻·运动·工业', family: 'B' },
    ]},
]

interface Props {
  onSend: (text: string) => void
  onFilesAdded: (files: FileList) => void
  disabled: boolean
  styleTag: string | null
  onStyleTagChange: (id: string | null) => void
  fileTags: FileTag[]
  onRemoveFile: (i: number) => void
}

export function InputArea({ onSend, onFilesAdded, disabled, styleTag, onStyleTagChange, fileTags, onRemoveFile }: Props) {
  const [text, setText] = useState('')
  const [showStyles, setShowStyles] = useState(false)
  const ref = useRef<HTMLTextAreaElement>(null)
  const popRef = useRef<HTMLDivElement>(null)
  const fileRef = useRef<HTMLInputElement>(null)
  const hasTags = !!styleTag || fileTags.length > 0

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (popRef.current && !popRef.current.contains(e.target as Node)) setShowStyles(false)
    }
    if (showStyles) document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [showStyles])

  const handleSend = () => {
    if (!text.trim() || disabled) return
    onSend(text)
    setText('')
  }

  const allStyles = STYLES.flatMap(f => f.items)
  const activeStyle = allStyles.find(s => s.id === styleTag)

  return (
    <div id="chat-input-area">
      {hasTags && (
        <div id="input-tags">
          {styleTag && activeStyle && (
            <span className="input-tag style-tag">
              <span className="tag-dot" style={{ background: activeStyle.hex }} />
              {activeStyle.name}
              <button className="tag-x" onClick={() => onStyleTagChange(null)}>×</button>
            </span>
          )}
          {fileTags.map((f, i) => (
            <span className="input-tag file-tag" key={i}>
              📄 {f.name}
              <button className="tag-x" onClick={() => onRemoveFile(i)}>×</button>
            </span>
          ))}
        </div>
      )}
      <textarea
        ref={ref}
        id="chat-input"
        value={text}
        onChange={e => setText(e.target.value)}
        onKeyDown={e => {
          if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() }
        }}
        placeholder={disabled ? '正在处理中…' : '描述你想要的 PPT…\n例如：「帮我把这篇论文转成组会 PPT，8 页左右」'}
        rows={hasTags ? 2 : 3}
        disabled={disabled}
      />
      <div id="input-actions">
        <label id="file-upload-label" title="上传文件">
          <span className="icon">📎</span> 附件
          <input ref={fileRef} type="file" accept=".pdf,.docx,.md,.txt,.zip" multiple hidden
            onChange={e => { if (e.target.files?.length) { onFilesAdded(e.target.files); e.target.value = '' } }} />
        </label>
        <div className="style-picker-wrap" ref={popRef}>
          <button className="btn-action" title="选择风格"
            onClick={() => setShowStyles(!showStyles)} disabled={disabled}>
            <span className="icon">🎨</span> 风格
          </button>
          {showStyles && (
            <div className="style-popover">
              {STYLES.map(fam => (
                <div key={fam.family} className="style-pop-family">
                  <span className="style-pop-label">{fam.label}</span>
                  <span className="style-pop-desc">{fam.desc}</span>
                  <div className="style-pop-chips">
                    {fam.items.map(s => (
                      <button key={s.id}
                        className={`style-pop-chip${styleTag === s.id ? ' active' : ''}`}
                        onClick={() => { onStyleTagChange(styleTag === s.id ? null : s.id); setShowStyles(false) }}>
                        <span className="spc-dot" style={{background:s.hex}} />
                        <span className="spc-name">{s.name}</span>
                        <span className="spc-sub">{s.desc}</span>
                      </button>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
        <button className="btn btn-primary" onClick={handleSend} disabled={disabled}>发送</button>
      </div>
    </div>
  )
}
