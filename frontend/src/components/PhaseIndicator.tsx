import type { PipelinePhase } from '../types/messages'

interface Props {
  phase: PipelinePhase
  slideCount: Record<number, string>
  slideTotal: number
}

const LABELS: Record<string, string> = {
  idle:'待输入', planning:'规划中', generating:'正在生成', reviewing:'审查中', done:'已完成',
}
const COLORS: Record<string, string> = {
  idle:'#7a8ba0', planning:'#d29922', generating:'#4a90d9', reviewing:'#d29922', done:'#3fb950',
}

export function PhaseIndicator({ phase, slideCount, slideTotal }: Props) {
  const gen = Object.keys(slideCount).length
  return (
    <div id="preview-header">
      <span className="title">幻灯片预览</span>
      <div style={{display:'flex',alignItems:'center',gap:12}}>
        <span style={{fontFamily:'var(--font-mono)',fontSize:11,color:'var(--text-dim)'}}>
          {slideTotal > 0 ? `${gen} / ${slideTotal}` : ''}
        </span>
        <span id="phase-indicator" style={{borderColor:COLORS[phase]||'#1e3d66',color:COLORS[phase]||'#7a8ba0'}}>
          {LABELS[phase] || phase}
        </span>
      </div>
    </div>
  )
}
