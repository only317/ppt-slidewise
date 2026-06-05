import type { OutlineData } from '../types/messages'

interface Props {
  outline: OutlineData
  onConfirm: (approved: boolean) => void
}

const LAYOUT_LABELS: Record<string, string> = {
  L1:'L1-封面', L2:'L2-章节', L3:'L3-要点', L4:'L4-图文', L5:'L5-对比', L6:'L6-数据', L7:'L7-封底',
}

export function OutlineEditor({ outline, onConfirm }: Props) {
  return (
    <div className="outline-card">
      <div className="oc-header">内容大纲 · {outline.pages.length} 页</div>

      {outline.pages.map(p => (
        <div className="outline-row" key={p.index}>
          <span className="idx">{String(p.index).padStart(2, '0')}</span>
          <input defaultValue={p.title} data-page={p.index} data-field="title" />
          <select defaultValue={p.layout} data-page={p.index} data-field="layout">
            {Object.entries(LAYOUT_LABELS).map(([k, v]) => (
              <option value={k} key={k}>{v}</option>
            ))}
          </select>
        </div>
      ))}

      <div className="action-row">
        <button className="btn btn-success" onClick={() => onConfirm(true)}>确认并生成</button>
        <button className="btn btn-ghost" onClick={() => onConfirm(false)}>先编辑再生成</button>
      </div>
    </div>
  )
}
