import type { OutlineData } from '../types/messages'

interface Props { outline: OutlineData }

export function DesignPreview({ outline }: Props) {
  const spec = outline.design_spec || outline.meta || {}
  const colors: [string, string][] = []
  for (const [k, v] of Object.entries(spec)) {
    if (typeof v === 'string' && v.startsWith('#')) colors.push([k, v])
  }

  return (
    <div className="design-preview">
      <div className="dp-header">设计方案</div>

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
    </div>
  )
}
