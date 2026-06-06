import type { ReviewReportData } from '../types/messages'

interface Props {
  report: ReviewReportData
  onFix: (pages: number[], ignore: number[], feedback?: string) => void
  onSkip: () => void
}

const SEV_LABELS: Record<string, string> = {
  error:'严重', warning:'警告', suggestion:'建议',
}

export function ReviewReport({ report, onFix, onSkip }: Props) {
  const issues = report.issues || []
  const [feedback, setFeedback] = (window as any).__reviewFeedback = (window as any).__reviewFeedback || ''
  const setFb = (v: string) => { (window as any).__reviewFeedback = v }

  return (
    <div className="outline-card">
      <div className="oc-header">审查报告 · 第 {report.current_round}/{report.max_rounds} 轮</div>
      {report.summary && <p style={{fontSize:12,color:'var(--text-muted)',marginBottom:12}}>{report.summary}</p>}

      {issues.length === 0 ? (
        <p style={{fontSize:13,color:'var(--accent-ok)'}}>所有页面均通过审查，可以直接导出。</p>
      ) : (
        issues.map((iss, i) => (
          <div className={`issue-card ${iss.severity}`} key={i}>
            <div className="issue-head">
              <span className="issue-sev">{SEV_LABELS[iss.severity] || iss.severity}</span>
              <span className="issue-cat">{iss.category} · 第{iss.page}页</span>
            </div>
            <div className="issue-desc">{iss.description}</div>
            {iss.suggestion && <div className="issue-sug">→ {iss.suggestion}</div>}
          </div>
        ))
      )}

      <textarea className="review-feedback-input"
        placeholder="补充修改意见（可选）…"
        defaultValue={(window as any).__reviewFeedback || ''}
        onChange={e => setFb(e.target.value)}
        rows={2}
      />

      <div className="action-row">
        <button className="btn btn-success"
          onClick={() => onFix(issues.map(i => i.page), [], (window as any).__reviewFeedback || '')}>
          修复全部问题
        </button>
        <button className="btn btn-warning"
          onClick={() => onFix(issues.filter(i => i.severity === 'error').map(i => i.page), [], (window as any).__reviewFeedback || '')}>
          仅修复严重问题
        </button>
        <button className="btn btn-ghost" onClick={onSkip}>跳过 → 直接导出</button>
      </div>
    </div>
  )
}
