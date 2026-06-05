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

// ---- App ----
export default function App() {
  const [outline, setOutline] = useState<OutlineData | null>(null)
  const [slides, setSlides] = useState<Record<number, string>>({})
  const [review, setReview] = useState<ReviewReportData | null>(null)
  const [done, setDone] = useState<DoneData | null>(null)
  const [errors, setErrors] = useState<string[]>([])
  const [toasts, setToasts] = useState<string[]>([])
  const [lightboxIndex, setLightboxIndex] = useState<number | null>(null)
  const slideCount = useRef(0)

  const toast = useCallback((msg: string) => {
    setToasts(t => [...t, msg])
    setTimeout(() => setToasts(t => t.filter(m => m !== msg)), 3000)
  }, [])

  const handleMessage = useCallback((msg: ServerMessage) => {
    switch (msg.type) {
      case 'outline':
        setOutline(msg.data)
        slideCount.current = msg.data.pages.length
        // Will trigger skeleton slides in SlideGrid
        break
      case 'slide_generated':
        setSlides(s => ({ ...s, [msg.data.index]: msg.data.svg }))
        break
      case 'review_report':
        setReview(msg.data)
        break
      case 'slide_fixed':
        setSlides(s => ({ ...s, [msg.data.index]: msg.data.svg }))
        break
      case 'done':
        setDone(msg.data)
        toast('PPTX 已生成，可下载')
        break
      case 'error':
        setErrors(e => [...e, msg.data.message].slice(-5))
        if (!msg.data.recoverable) setDone(null)
        break
      case 'state_sync':
        if (msg.data.outline) setOutline(msg.data.outline)
        if (msg.data.slides) setSlides(msg.data.slides)
        if (msg.data.review) setReview(msg.data.review)
        break
    }
  }, [toast])

  const { phase, connected, sendMessage, confirmOutline, fixDecisions, requestDownload } = useWebSocket(handleMessage)

  // Drop zone
  const [dragging, setDragging] = useState(false)
  const [uploadedFiles, setUploadedFiles] = useState<UploadedFile[]>([])

  const handleFiles = useCallback(async (files: FileList) => {
    const result: UploadedFile[] = []
    for (const file of files) {
      result.push({ name: file.name, content_base64: await fileToBase64(file), type: file.type })
    }
    setUploadedFiles(f => [...f, ...result])
    toast(`已添加 ${files.length} 个文件`)
  }, [toast])

  const handleSend = useCallback((text: string) => {
    if (!text.trim()) return
    sendMessage(text, uploadedFiles)
    setUploadedFiles([])
  }, [sendMessage, uploadedFiles])

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
  }, [confirmOutline])

  const handleFix = useCallback((pages: number[], ignore: number[], feedback = '') => {
    fixDecisions(pages, ignore, feedback)
  }, [fixDecisions])

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
        onSend={handleSend}
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
      {/* Drag handlers */}
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
  window.addEventListener('dragover', (e) => { e.preventDefault(); /* set by App */ })
}
