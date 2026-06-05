import type { OutlineData } from '../types/messages'

interface Props { outline: OutlineData }

const PALETTE_NAMES: Record<string, string> = {
  indigo: '靛蓝 Indigo', ink: '墨水 Ink', forest: '森林 Forest', dune: '沙丘 Dune',
  'klein-blue': '克莱因蓝 Klein Blue', lemon: '柠檬黄 Lemon',
  lime: '柠绿 Lime', 'safety-orange': '安全橙 Safety Orange',
}

export function DesignPreview({ outline }: Props) {
  const spec = outline.design_spec || outline.meta || {}
  const paletteId = String(spec.palette || spec.palette_name || '')
  const paletteName = PALETTE_NAMES[paletteId] || paletteId

  const colors: [string, string][] = []
  for (const [k, v] of Object.entries(spec)) {
    if (typeof v === 'string' && v.startsWith('#')) colors.push([k, v])
  }

  return (
    <div className="design-preview">
      <div className="dp-header">
        设计方案
        {paletteName && <span className="dp-palette-name">{paletteName}</span>}
      </div>

      {colors.length > 0 && (
        <div className="palette-row">
          {colors.slice(0, 6).map(([name, hex]) => (
            <div className="palette-dot" key={name}>
              <div className="dot" style={{ background: hex }} />
              <span className="label">{hex}</span>
            </div>
          ))}
        </div>
      )}

      <div className="typo-preview">
        <div className="level"><span className="tag">H1</span><span style={{fontSize:32,fontWeight:200,color:'var(--text)'}}>封面标题 72-96</span><span className="spec">ExtraLight</span></div>
        <div className="level"><span className="tag">H2</span><span style={{fontSize:24,fontWeight:200,color:'var(--text)'}}>章节标题 48-64</span><span className="spec">ExtraLight</span></div>
        <div className="level"><span className="tag">H3</span><span style={{fontSize:18,fontWeight:300,color:'var(--text)'}}>页面标题 36-48</span><span className="spec">Light</span></div>
        <div className="level"><span className="tag">正文</span><span style={{fontSize:15,fontWeight:400,color:'var(--text)'}}>正文 14-18</span><span className="spec">Regular</span></div>
        <div className="level"><span className="tag">标注</span><span style={{fontSize:11,fontWeight:500,color:'var(--text-muted)'}}>页码 10-12</span><span className="spec">Medium</span></div>
      </div>

      <div className="dp-switch-hint">
        想换风格？输入「切换为克莱因蓝」即可一键切换
      </div>
    </div>
  )
}
