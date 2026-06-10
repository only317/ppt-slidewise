import type { OutlineData } from '../types/messages'

interface Props {
  outline: OutlineData
  onConfirm: (approved: boolean) => void
}

const LAYOUT_LABELS: Record<string, string> = {
  L1:'L1-\u5c01\u9762', L2:'L2-\u7ae0\u8282', L3:'L3-\u8981\u70b9', L4:'L4-\u56fe\u6587', L5:'L5-\u5bf9\u6bd4', L6:'L6-\u6570\u636e', L7:'L7-\u5c01\u5e95',
}

export function OutlineEditor({ outline, onConfirm }: Props) {
  return (
    <div className="outline-card">
      <div className="oc-header">{'\u5185\u5bb9\u5927\u7eb2 \u00b7 '}{outline.pages.length}{' \u9875'}</div>

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
        <button className="btn btn-success" onClick={() => onConfirm(false)}>
          {'\u786e\u8ba4\u5e76\u751f\u6210'}
        </button>
      </div>
    </div>
  )
}
