import { useState, useCallback, useRef } from 'react'
import type { ServerMessage, SlideData, OutlineData, ReviewReportData, DoneData, UploadedFile } from './types/messages'
import { useWebSocket } from './hooks/useWebSocket'
import { ChatPanel } from './components/ChatPanel'
import { SlideGrid } from './components/SlideGrid'
import { Lightbox } from './components/Lightbox'
import { PhaseIndicator } from './components/PhaseIndicator'
import { DropZone } from './components/DropZone'
import { Toast } from './components/Toast'
import './App.css'

// ---- File helpers ----
function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve((reader.result as string).split(',')[1])
    reader.onerror = reject
    reader.readAsDataURL(file)
  })
}

interface FileTag { name: string }

// ---- App ----
export default function App() {
  const [outline, setOutline] = useState<OutlineData | null>(null)
  const [slides, setSlides] = useState<Record<number, string>>({})
  const [review, setReview] = useState<ReviewReportData | null>(null)
  const [done, setDone] = useState<DoneData | null>(null)
  const [errors, setErrors] = useState<string[]>([])
  const [toasts, setToasts] = useState<string[]>([])
  const [statusMessages, setStatusMessages] = useState<string[]>([])
  const [lightboxIndex, setLightboxIndex] = useState<number | null>(null)
  const [styleTag, setStyleTag] = useState<string | null>(null)
  const [fileTags, setFileTags] = useState<FileTag[]>([])
  const [uploadedFiles, setUploadedFiles] = useState<UploadedFile[]>([])
  const [dragging, setDragging] = useState(false)
  const slideCount = useRef(0)

  const addStatus = useCallback((msg: string) => {
    setStatusMessages(s => [...s, msg])
  }, [])

  const toast = useCallback((msg: string) => {
    setToasts(t => [...t, msg])
    setTimeout(() => setToasts(t => t.filter(m => m !== msg)), 3000)
  }, [])

  const handleMessage = useCallback((msg: ServerMessage) => {
    switch (msg.type) {
      case 'outline':
        setOutline(msg.data)
        slideCount.current = msg.data.pages.length
        addStatus('大纲已生成，请确认或修改后继续')
        break
      case 'slide_generated':
        setSlides(s => ({ ...s, [msg.data.index]: msg.data.svg }))
        addStatus(`已生成第 ${msg.data.index}/${slideCount.current} 页`)
        break
      case 'review_report':
        setReview(msg.data)
        addStatus(`评审完成：${msg.data.summary}`)
        break
      case 'slide_fixed':
        setSlides(s => ({ ...s, [msg.data.index]: msg.data.svg }))
        addStatus(`第 ${msg.data.index} 页已修复`)
        break
      case 'done':
        setDone(msg.data)
        setStatusMessages([])
        toast('PPTX 已生成，可下载')
        break
      case 'error':
        setErrors(e => [...e, msg.data.message].slice(-5))
        addStatus(`错误：${msg.data.message}`)
        if (!msg.data.recoverable) setDone(null)
        break
      case 'state_sync':
        if (msg.data.outline) setOutline(msg.data.outline)
        if (msg.data.slides) setSlides(msg.data.slides)
        if (msg.data.review) setReview(msg.data.review)
        if (msg.data.phase && msg.data.phase !== 'idle') {
          addStatus('会话已恢复')
        }
        break
    }
  }, [toast, addStatus])

  const { phase, connected, sendMessage, confirmOutline, fixDecisions, requestDownload } = useWebSocket(handleMessage)

  const handleFiles = useCallback(async (files: FileList) => {
    const result: UploadedFile[] = []
    const tags: FileTag[] = []
    for (const file of files) {
      result.push({ name: file.name, content_base64: await fileToBase64(file), type: file.type })
      tags.push({ name: file.name })
    }
    setUploadedFiles(f => [...f, ...result])
    setFileTags(f => [...f, ...tags])
    addStatus(`已添加 ${files.length} 个文件`)
  }, [addStatus])

  const handleRemoveFile = useCallback((i: number) => {
    setFileTags(f => f.filter((_, j) => j !== i))
    setUploadedFiles(f => f.filter((_, j) => j !== i))
  }, [])

  const handleSend = useCallback((text: string) => {
    if (!text.trim() && !uploadedFiles.length) return
    // Build message with style context
    let fullText = text
    if (styleTag && !text.includes(styleTag)) {
      const names: Record<string, string> = {
        'indigo': '靛蓝', 'ink': '墨水', 'forest': '森林', 'dune': '沙丘',
        'klein-blue': '克莱因蓝', 'lemon': '柠檬黄', 'lime': '柠绿', 'safety-orange': '安全橙',
      }
      fullText = `用${names[styleTag] || styleTag}风格。` + text
    }
    setStatusMessages([])
    addStatus('正在分析输入内容…')
    sendMessage(fullText, uploadedFiles)
    setUploadedFiles([])
    setFileTags([])
  }, [sendMessage, uploadedFiles, styleTag, addStatus])

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
    setStatusMessages([])
    if (approved) addStatus('大纲已确认，开始生成幻灯片…')
  }, [confirmOutline, addStatus])

  const handleFix = useCallback((pages: number[], ignore: number[], feedback = '') => {
    fixDecisions(pages, ignore, feedback)
    setStatusMessages([])
    if (pages.length) addStatus(`正在修复第 ${pages.join('、')} 页…`)
  }, [fixDecisions, addStatus])

  const slideKeys = Object.keys(slides).map(Number).sort((a, b) => a - b)

  return (
    <div id="app">
      <ChatPanel
        phase={phase}
        connected={connected}
        outline={outline}
        review={review}
        done={done}
        errors={errors}
        statusMessages={statusMessages}
        styleTag={styleTag}
        fileTags={fileTags}
        onStyleTagChange={setStyleTag}
        onRemoveFile={handleRemoveFile}
        onSend={handleSend}
        onFilesAdded={handleFiles}
        onConfirmOutline={handleConfirmOutline}
        onFix={handleFix}
        onSkipReview={requestDownload}
        onDismissError={(i) => setErrors(e => e.filter((_, j) => j !== i))}
      />
      <div id="preview-panel">
        <PhaseIndicator phase={phase} slideCount={slides} slideTotal={outline?.pages.length || slideCount.current} />
        <SlideGrid
          outline={outline}
          slides={slides}
          onSlideClick={setLightboxIndex}
        />
      </div>
      <Lightbox
        index={lightboxIndex}
        slides={slides}
        slideKeys={slideKeys}
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
          e.preventDefault()
          setDragging(false)
          if (e.dataTransfer.files.length > 0) await handleFiles(e.dataTransfer.files)
        }}
      />
    </div>
  )
}

// Global drag handlers
if (typeof window !== 'undefined') {
  window.addEventListener('dragover', (e) => { e.preventDefault() })
}
