import { useState, useRef } from 'react'

interface Props {
  onSend: (text: string) => void
  disabled: boolean
}

export function InputArea({ onSend, disabled }: Props) {
  const [text, setText] = useState('')
  const ref = useRef<HTMLTextAreaElement>(null)

  const handleSend = () => {
    if (!text.trim() || disabled) return
    onSend(text)
    setText('')
  }

  return (
    <div id="chat-input-area">
      <textarea
        ref={ref}
        id="chat-input"
        value={text}
        onChange={e => setText(e.target.value)}
        onKeyDown={e => {
          if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() }
        }}
        placeholder={disabled ? '正在处理中…' : '描述你想要的 PPT…\n例如：「帮我把这篇论文转成靛蓝色组会 PPT，8 页左右」'}
        rows={3}
        disabled={disabled}
      />
      <div id="input-actions">
        <label id="file-upload-label">
          <span className="icon">+</span> 添加附件
          <input type="file" accept=".pdf,.docx,.md,.txt" multiple hidden />
        </label>
        <button className="btn btn-primary" onClick={handleSend} disabled={disabled}>发送</button>
      </div>
    </div>
  )
}
