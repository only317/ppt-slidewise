import { useState, useRef, useEffect } from 'react'

interface FileTag { name: string }

interface StyleItem { id: string; name: string; hex: string; family: 'dark' | 'light' }

const STYLES: { family: string; items: StyleItem[] }[] = [
  { family: '深色系', items: [
    { id: 'indigo', name: '靛蓝', hex: '#4a90d9', family: 'dark' },
    { id: 'ink', name: '墨水', hex: '#c9a96e', family: 'dark' },
    { id: 'forest', name: '森林', hex: '#7a9a6e', family: 'dark' },
    { id: 'dune', name: '沙丘', hex: '#d4956a', family: 'dark' },
  ]},
  { family: '亮色系', items: [
    { id: 'klein-blue', name: '克莱因蓝', hex: '#002FA7', family: 'light' },
    { id: 'lemon', name: '柠檬黄', hex: '#c8a200', family: 'light' },
    { id: 'lime', name: '柠绿', hex: '#7a9900', family: 'light' },
    { id: 'safety-orange', name: '安全橙', hex: '#d45a2e', family: 'light' },
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

  const activeStyle = STYLES.flatMap(f => f.items).find(s => s.id === styleTag)

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
                  <span className="style-pop-label">{fam.family}</span>
                  <div className="style-pop-chips">
                    {fam.items.map(s => (
                      <button key={s.id}
                        className={`style-pop-chip${styleTag === s.id ? ' active' : ''}`}
                        onClick={() => { onStyleTagChange(styleTag === s.id ? null : s.id); setShowStyles(false) }}>
                        <span className="spc-dot" style={{background:s.hex}} />
                        <span className="spc-name">{s.name}</span>
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
