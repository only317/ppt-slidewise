import { useState, useCallback, useRef } from 'react'
import type { ServerMessage, OutlineData, ReviewReportData, DoneData, UploadedFile, AgentThinkingData, AgentMessageData, PageFixedConfirmData, FixBatchDoneData } from './types/messages'
import { useWebSocket } from './hooks/useWebSocket'
import { ChatPanel } from './components/ChatPanel'
import type { ChatEntry } from './components/ChatPanel'
import { SlideGrid } from './components/SlideGrid'
import { Lightbox } from './components/Lightbox'
import { PhaseIndicator } from './components/PhaseIndicator'
import { DropZone } from './components/DropZone'
import { Toast } from './components/Toast'
import './App.css'

function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve((reader.result as string).split(',')[1])
    reader.onerror = reject
    reader.readAsDataURL(file)
  })
}

interface FileTag { name: string }

export default function App() {
  const [outline, setOutline] = useState<OutlineData | null>(null)
  const [slides, setSlides] = useState<Record<number, string>>({})
  const [review, setReview] = useState<ReviewReportData | null>(null)
  const [done, setDone] = useState<DoneData | null>(null)
  const [toasts, setToasts] = useState<string[]>([])
  const [fixedPages, setFixedPages] = useState<Set<number>>(new Set())
  const [oldSlides, setOldSlides] = useState<Record<number, string>>({})
  const [lightboxIndex, setLightboxIndex] = useState<number | null>(null)
  const [styleTag, setStyleTag] = useState<string | null>(null)
  const [fileTags, setFileTags] = useState<FileTag[]>([])
  const [uploadedFiles, setUploadedFiles] = useState<UploadedFile[]>([])
  const [dragging, setDragging] = useState(false)
  const [chatHistory, setChatHistory] = useState<ChatEntry[]>([
    { role: 'assistant', type: 'welcome' },
  ])
  const slideCount = useRef(0)

  const addChat = useCallback((entry: ChatEntry) => {
    setChatHistory(h => [...h, entry])
  }, [])

  const toast = useCallback((msg: string) => {
    setToasts(t => [...t, msg])
    setTimeout(() => setToasts(t => t.filter(m => m !== msg)), 3000)
  }, [])

  const handleMessage = useCallback((msg: ServerMessage) => {
    switch (msg.type) {
      case 'outline':
        // Clear non-essential entries from previous rounds
        setChatHistory(h => h.filter(e =>
          !('type' in e) || (e.type !== 'agent_thinking' && e.type !== 'status')
        ))
        setSlides({})
        setFixedPages(new Set())
        setOldSlides({})
        setReview(null)
        setDone(null)
        setOutline(msg.data)
        slideCount.current = msg.data.pages.length
        addChat({ role: 'assistant', type: 'outline', data: msg.data })
        break
      case 'slide_generated':
        setSlides(s => ({ ...s, [msg.data.index]: msg.data.svg }))
        if (msg.data.index === 1 || msg.data.index % 3 === 0 || msg.data.index === slideCount.current) {
          addChat({ role: 'system', type: 'status', text: `正在生成第 ${msg.data.index}/${slideCount.current} 页…` })
        }
        break
      case 'review_report':
        // Clear thinking entries from generation phase
        setChatHistory(h => h.filter(e =>
          !('type' in e) || e.type !== 'agent_thinking'
        ))
        setReview(msg.data)
        setFixedPages(new Set())
        setOldSlides({})
        addChat({ role: 'assistant', type: 'review', data: msg.data })
        break
      case 'slide_fixed':
        setSlides(s => {
          if (s[msg.data.index]) setOldSlides(o => ({ ...o, [msg.data.index]: s[msg.data.index] }))
          return { ...s, [msg.data.index]: msg.data.svg }
        })
        setFixedPages(prev => new Set(prev).add(msg.data.index))
        {
          const oldSvg = slides[msg.data.index] || ''
          if (oldSvg) {
            addChat({ role: 'assistant', type: 'slide_diff', index: msg.data.index, oldSvg, newSvg: msg.data.svg })
          } else {
            addChat({ role: 'system', type: 'status', text: `\u7b2c${msg.data.index} \u9875\u5df2\u4fee\u590d` })
          }
        }
        break
      case 'agent_thinking':
        addChat({ role: 'assistant', type: 'agent_thinking', data: msg.data })
        break
      case 'agent_message':
        addChat({ role: 'assistant', type: 'agent_message', data: msg.data })
        break
      case 'page_fixed_confirm':
        addChat({ role: 'assistant', type: 'page_fixed_confirm', data: msg.data })
        break
      case 'fix_batch_done':
        addChat({ role: 'assistant', type: 'fix_batch_done', data: msg.data })
        break
      case 'done':
        setDone(msg.data)
        addChat({ role: 'assistant', type: 'done', data: msg.data })
        toast('PPTX 已生成，可下载')
        break
      case 'error':
        addChat({ role: 'system', type: 'error', text: msg.data.message })
        if (!msg.data.recoverable) setDone(null)
        break
      case 'state_sync':
        if (msg.data.outline) {
          setOutline(msg.data.outline)
          slideCount.current = msg.data.outline.pages?.length || 0
        }
        if (msg.data.slides) setSlides(msg.data.slides)
        if (msg.data.review) setReview(msg.data.review)
        // Rebuild chat from restored state (only if we don't have it yet)
        setChatHistory(prev => {
          if (prev.length > 1) return prev  // already restored
          const h: ChatEntry[] = [{ role: 'assistant', type: 'welcome' as const }]
          if (msg.data.outline) h.push({ role: 'assistant', type: 'outline', data: msg.data.outline as OutlineData })
          if (msg.data.review) h.push({ role: 'assistant', type: 'review', data: msg.data.review as ReviewReportData })
          h.push({ role: 'system', type: 'status', text: '会话已恢复' })
          return h
        })
        break
    }
  }, [toast, addChat])

  const { phase, connected, sessions, sendMessage, confirmOutline, fixDecisions, confirmPageFix, undoFix, requestDownload, cancel } = useWebSocket(handleMessage)

  const handleFiles = useCallback(async (files: FileList) => {
    const result: UploadedFile[] = []
    const tags: FileTag[] = []
    for (const file of files) {
      result.push({ name: file.name, content_base64: await fileToBase64(file), type: file.type })
      tags.push({ name: file.name })
    }
    setUploadedFiles(f => [...f, ...result])
    setFileTags(f => [...f, ...tags])
  }, [])

  const handleRemoveFile = useCallback((i: number) => {
    setFileTags(f => f.filter((_, j) => j !== i))
    setUploadedFiles(f => f.filter((_, j) => j !== i))
  }, [])

  const handleSend = useCallback((text: string) => {
    if (!text.trim() && !uploadedFiles.length) return
    let fullText = text
    if (styleTag && !text.includes(styleTag)) {
      const names: Record<string, string> = {
        'ink': '墨水经典', 'indigo': '靛蓝瓷', 'forest': '森林墨', 'kraft': '牛皮纸', 'dune': '沙丘',
        'klein-blue': '克莱因蓝', 'lemon': '柠檬黄', 'lime': '柠绿', 'safety-orange': '安全橙',
      }
      fullText = `用${names[styleTag] || styleTag}风格。${text}`
    }
    addChat({ role: 'user', text: fullText })
    addChat({ role: 'system', type: 'status', text: '正在分析…' })
    sendMessage(fullText, uploadedFiles)
    setUploadedFiles([])
    setFileTags([])
    setStyleTag(null)
  }, [sendMessage, uploadedFiles, styleTag, addChat])

  const handleConfirmOutline = useCallback((approved: boolean) => {
    const pages: Record<string, unknown>[] = []
    document.querySelectorAll('.outline-row').forEach(row => {
      const input = row.querySelector('[data-field="title"]') as HTMLInputElement
      const select = row.querySelector('[data-field="layout"]') as HTMLSelectElement
      if (input && select) {
        pages.push({ index: parseInt(input.dataset.page!), title: input.value, layout: select.value, bullets: [] })
      }
    })
    confirmOutline(approved, approved ? [] : pages)
    setReview(null)
    setFixedPages(new Set())
  }, [confirmOutline])

  const handleFix = useCallback((pages: number[], ignore: number[], feedback = '') => {
    fixDecisions(pages, ignore, feedback)
  }, [fixDecisions])

  const handleConfirmPageFix = useCallback((index: number, approved: boolean, feedback?: string) => {
    confirmPageFix(index, approved, feedback || '')
  }, [confirmPageFix])

  const handleUndoFix = useCallback(() => {
    undoFix()
  }, [undoFix])

  const slideKeys = Object.keys(slides).map(Number).sort((a, b) => a - b)

  return (
    <div id="app">
      <ChatPanel
        chatHistory={chatHistory}
        sessions={sessions}
        outline={outline}
        review={review}
        done={done}
        phase={phase}
        styleTag={styleTag}
        fileTags={fileTags}
        onStyleTagChange={setStyleTag}
        onRemoveFile={handleRemoveFile}
        onSend={handleSend}
        onFilesAdded={handleFiles}
        onConfirmOutline={handleConfirmOutline}
        onFix={handleFix}
        onSkipReview={requestDownload}
        onConfirmPageFix={handleConfirmPageFix}
        onUndoFix={handleUndoFix}
      />
      <div id="preview-panel">
        <PhaseIndicator phase={phase} slideCount={slides} slideTotal={outline?.pages.length || slideCount.current} onCancel={cancel} />
        <SlideGrid outline={outline} slides={slides} onSlideClick={setLightboxIndex} review={review} phase={phase} />
      </div>
      <Lightbox
        index={lightboxIndex} slides={slides} slideKeys={slideKeys}
        onClose={() => setLightboxIndex(null)}
        onPrev={() => {
          const idx = slideKeys.indexOf(lightboxIndex!)
          if (idx > 0) setLightboxIndex(slideKeys[idx - 1])
        }}
        onNext={() => {
          const idx = slideKeys.indexOf(lightboxIndex!)
          if (idx < slideKeys.length - 1) setLightboxIndex(slideKeys[idx + 1])
        }}
      />
      <DropZone active={dragging} onFiles={handleFiles} />
      {toasts.map((msg, i) => <Toast key={i} message={msg} />)}
      <div
        style={{ display: dragging ? 'block' : 'none', position: 'fixed', inset: 0, zIndex: 9999 }}
        onDragLeave={() => setDragging(false)}
        onDrop={async (e) => {
          e.preventDefault(); setDragging(false)
          if (e.dataTransfer.files.length > 0) await handleFiles(e.dataTransfer.files)
        }}
      />
    </div>
  )
}

if (typeof window !== 'undefined') {
  window.addEventListener('dragover', (e) => { e.preventDefault() })
}
