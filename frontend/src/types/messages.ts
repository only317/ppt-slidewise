// ---- Server → Client ----
export interface OutlinePage {
  index: number
  title: string
  layout: string
  bullets: string[]
  notes: string
}

export interface OutlineData {
  pages: OutlinePage[]
  design_spec: Record<string, string>
  meta: Record<string, unknown>
}

export interface SlideData {
  index: number
  svg: string
  layout: string
}

export interface ReviewIssue {
  page: number
  severity: 'error' | 'warning' | 'suggestion'
  category: string
  description: string
  suggestion: string
  element_id: string
}

export interface ReviewReportData {
  issues: ReviewIssue[]
  summary: string
  current_round: number
  max_rounds: number
}

export interface DoneData {
  download_url: string
  filename: string
  session_id: string
}

export interface ErrorData {
  message: string
  phase: string
  recoverable: boolean
}

export interface StateSyncData {
  session_id: string
  phase: PipelinePhase
  outline?: OutlineData
  slides?: Record<number, string>
  review?: ReviewReportData
}

export interface SessionSummary {
  session_id: string
  phase: string
  created_at: string
  slides_generated: number
  slides_total: number
}

// ---- Client → Server ----
export interface UploadedFile {
  name: string
  content_base64: string
  type: string
}

// ---- Agent Conversational ----
export interface AgentThinkingData {
  agent: string       // 'strategist' | 'generator' | 'reviewer'
  text: string
  tool_name: string
  tool_args: string
}

export interface AgentMessageData {
  agent: string
  text: string
  markdown: boolean
}

export interface PageFixedConfirmData {
  index: number
  svg: string
  old_svg: string
  fix_round: number
}

export interface FixBatchDoneData {
  fixed_pages: number[]
  total_issues_remaining: number
}

// ---- Message Union ----
export type PipelinePhase = 'idle' | 'planning' | 'generating' | 'reviewing' | 'done'

export type ServerMessage =
  | { type: 'outline'; data: OutlineData }
  | { type: 'slide_generated'; data: SlideData }
  | { type: 'review_report'; data: ReviewReportData }
  | { type: 'slide_fixed'; data: SlideData }
  | { type: 'done'; data: DoneData }
  | { type: 'error'; data: ErrorData }
  | { type: 'state_sync'; data: StateSyncData }
  | { type: 'session_list'; data: SessionSummary[] }
  | { type: 'agent_thinking'; data: AgentThinkingData }
  | { type: 'agent_message'; data: AgentMessageData }
  | { type: 'page_fixed_confirm'; data: PageFixedConfirmData }
  | { type: 'fix_batch_done'; data: FixBatchDoneData }
