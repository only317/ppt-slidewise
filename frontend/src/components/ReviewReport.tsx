import { useState, useMemo } from 'react'
import type { ReviewReportData } from '../types/messages'

interface Props {
  report: ReviewReportData
  onFix: (pages: number[], ignore: number[], feedback?: string) => void
  onSkip: () => void
}

const SEV_LABELS: Record<string, string> = {
  error: '严重', warning: '警告', suggestion: '建议',
}
const SEV_ORDER: Record<string, number> = { error: 0, warning: 1, suggestion: 2 }

export function ReviewReport({ report, onFix, onSkip }: Props) {
  const issues = report.issues || []

  const pageMap = useMemo(() => {
    const map = new Map<number, typeof issues>()
    for (const iss of issues) {
      const arr = map.get(iss.page) || []
      arr.push(iss)
      map.set(iss.page, arr)
    }
    for (const arr of map.values()) {
      arr.sort((a, b) => (SEV_ORDER[a.severity] ?? 9) - (SEV_ORDER[b.severity] ?? 9))
    }
    return map
  }, [issues])

  const pageIndices = useMemo(() => [...pageMap.keys()].sort((a, b) => a - b), [pageMap])

  const [selected, setSelected] = useState<Set<number>>(() => new Set(pageIndices))
  const [pageFeedback, setPageFeedback] = useState<Record<number, string>>({})
  const [globalFeedback, setGlobalFeedback] = useState('')

  const togglePage = (pg: number) => {
    setSelected(prev => {
      const next = new Set(prev)
      next.has(pg) ? next.delete(pg) : next.add(pg)
      return next
    })
  }
  const selectAll = () => setSelected(new Set(pageIndices))
  const selectNone = () => setSelected(new Set())
  const selectErrorsOnly = () => {
    const errorPages = new Set(issues.filter(i => i.severity === 'error').map(i => i.page))
    setSelected(errorPages)
  }

  const handleConfirm = () => {
    const fix = [...selected].sort((a, b) => a - b)
    const ignore = pageIndices.filter(p => !selected.has(p))
    const parts: string[] = []
    if (globalFeedback.trim()) parts.push(globalFeedback.trim())
    for (const pg of fix) {
      const fb = pageFeedback[pg]?.trim()
      if (fb) parts.push('[第' + pg + '页] ' + fb)
    }
    onFix(fix, ignore, parts.join('\n'))
  }

  const errorCount = issues.filter(i => i.severity === 'error').length
  const warnCount = issues.filter(i => i.severity === 'warning').length
  const suggCount = issues.filter(i => i.severity === 'suggestion').length

  if (issues.length === 0) {
    return (
      <div className="outline-card">
        <div className="oc-header">审查报告 · 第 {report.current_round}/{report.max_rounds} 轮</div>
        <p style={{ fontSize: 13, color: 'var(--accent-ok)', margin: '8px 0' }}>
          所有页面均通过审查，可以直接导出。
        </p>
        <div className="action-row">
          <button className="btn btn-success" onClick={onSkip}>直接导出</button>
        </div>
      </div>
    )
  }

  return (
    <div className="outline-card">
      <div className="oc-header">审查报告 · 第 {report.current_round}/{report.max_rounds} 轮</div>

      <div className="review-summary-bar">
        {errorCount > 0 && <span className="rsb-tag rsb-error">{errorCount} 严重</span>}
        {warnCount > 0 && <span className="rsb-tag rsb-warn">{warnCount} 警告</span>}
        {suggCount > 0 && <span className="rsb-tag rsb-sugg">{suggCount} 建议</span>}
        <span className="rsb-pages">{pageIndices.length} 页有问题</span>
      </div>

      <div className="review-select-bar">
        <button className="btn-select" onClick={selectAll}>全选</button>
        <button className="btn-select" onClick={selectErrorsOnly}>仅严重</button>
        <button className="btn-select" onClick={selectNone}>清空</button>
        <span className="rsb-count">已选 {selected.size}/{pageIndices.length} 页</span>
      </div>

      <div className="review-pages">
        {pageIndices.map(pg => {
          const pageIssues = pageMap.get(pg)!
          const hasError = pageIssues.some(i => i.severity === 'error')
          const worstSev = hasError ? 'error' : pageIssues[0]?.severity || 'warning'
          const checked = selected.has(pg)

          return (
            <div key={pg} className={'review-page-card ' + (checked ? 'selected ' : '') + 'sev-' + worstSev}>
              <label className="rpc-header">
                <input type="checkbox" checked={checked} onChange={() => togglePage(pg)} />
                <span className="rpc-title">{'第 ' + pg + ' 页'}</span>
                <span className="rpc-issue-count">{pageIssues.length} 个问题</span>
                {hasError && <span className="rpc-badge error">{'严重'}</span>}
              </label>

              <div className="rpc-issues">
                {pageIssues.map((iss, i) => (
                  <div key={i} className="rpc-issue">
                    <span className={'rpc-sev ' + iss.severity}>{SEV_LABELS[iss.severity] || iss.severity}</span>
                    <span className="rpc-cat">{iss.category}</span>
                    <span className="rpc-desc">{iss.description}</span>
                    {iss.suggestion && <span className="rpc-sug">{'→ ' + iss.suggestion}</span>}
                  </div>
                ))}
              </div>

              {checked && (
                <input
                  className="rpc-feedback"
                  type="text"
                  placeholder={'这页的修改意见（可选）'}
                  value={pageFeedback[pg] || ''}
                  onChange={e => setPageFeedback(prev => ({ ...prev, [pg]: e.target.value }))}
                />
              )}
            </div>
          )
        })}
      </div>

      <textarea
        className="review-feedback-input"
        placeholder={'全局修改意见（可选）— 例如：所有标题加粗、统一页码格式'}
        value={globalFeedback}
        onChange={e => setGlobalFeedback(e.target.value)}
        rows={2}
      />

      <div className="action-row">
        <button className="btn btn-success" onClick={handleConfirm} disabled={selected.size === 0}>
          {'修复选中的 ' + selected.size + ' 页'}
        </button>
        <button className="btn btn-ghost" onClick={onSkip}>{'跳过 → 直接导出'}</button>
      </div>
    </div>
  )
}
