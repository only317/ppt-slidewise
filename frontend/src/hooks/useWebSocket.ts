import { useRef, useCallback, useEffect, useState } from 'react'
import type { PipelinePhase, ServerMessage, UploadedFile } from '../types/messages'

type MessageHandler = (msg: ServerMessage) => void

function getSessionId(): string {
  return new URLSearchParams(window.location.search).get('session') || 'new'
}

export function useWebSocket(onMessage: MessageHandler) {
  const wsRef = useRef<WebSocket | null>(null)
  const [phase, setPhase] = useState<PipelinePhase>('idle')
  const [connected, setConnected] = useState(false)
  const sidRef = useRef(getSessionId())

  const connect = useCallback(() => {
    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${proto}//${location.host}/ws/${sidRef.current}`
    const ws = new WebSocket(wsUrl)
    wsRef.current = ws

    ws.onopen = () => {
      setConnected(true)
      if (sidRef.current !== 'new') {
        ws.send(JSON.stringify({ type: 'resume_session', data: { session_id: sidRef.current } }))
      }
    }

    ws.onmessage = (e) => {
      try {
        const msg: ServerMessage = JSON.parse(e.data)
        if (msg.type === 'state_sync' && sidRef.current === 'new' && msg.data.session_id !== 'new') {
          window.history.replaceState(null, '', `?session=${msg.data.session_id}`)
          sidRef.current = msg.data.session_id
        }
        if (msg.type === 'state_sync') setPhase(msg.data.phase)
        else if (msg.type === 'outline') setPhase('planning')
        else if (msg.type === 'slide_generated') setPhase('generating')
        else if (msg.type === 'review_report') setPhase('reviewing')
        else if (msg.type === 'done') setPhase('done')
        else if (msg.type === 'error' && !msg.data.recoverable) setPhase('idle')
        onMessage(msg)
      } catch {
        // ignore parse errors
      }
    }

    ws.onclose = () => { setConnected(false); setTimeout(connect, 3000) }
    ws.onerror = () => ws.close()
  }, [onMessage])

  useEffect(() => { connect(); return () => wsRef.current?.close() }, [connect])

  const send = useCallback((msg: Record<string, unknown>) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(msg))
    }
  }, [])

  const sendMessage = useCallback((text: string, files: UploadedFile[]) => {
    send({ type: 'user_message', data: { text, files, style: '' } })
  }, [send])

  const confirmOutline = useCallback((approved: boolean, pages: Record<string, unknown>[]) => {
    send({ type: 'confirm_outline', data: { approved, modified_outline: approved ? undefined : pages, feedback: '' } })
  }, [send])

  const fixDecisions = useCallback((fix: number[], ignore: number[], feedback = '') => {
    send({ type: 'fix_decisions', data: { fix, ignore, feedback } })
  }, [send])

  const requestDownload = useCallback(() => {
    send({ type: 'download', data: {} })
  }, [send])

  return { phase, connected, sidRef, sendMessage, confirmOutline, fixDecisions, requestDownload }
}
