import { useMemo } from 'react'
import { SlideCard } from './SlideCard'
import type { ReviewReportData } from '../types/messages'

interface Props {
  outline: { pages: { index: number }[] } | null
  slides: Record<number, string>
  onSlideClick: (index: number) => void
  review?: ReviewReportData | null
  phase?: string
}

export function SlideGrid({ outline, slides, onSlideClick, review, phase }: Props) {
  const hasContent = outline && outline.pages.length > 0

  // Build a set of page indices that have issues, with worst severity
  const issueMap = useMemo(() => {
    const map = new Map<number, string>()
    if (review?.issues) {
      for (const iss of review.issues) {
        const existing = map.get(iss.page)
        if (!existing || iss.severity === 'error' || (iss.severity === 'warning' && existing === 'suggestion')) {
          map.set(iss.page, iss.severity)
        }
      }
    }
    return map
  }, [review])

  const showIssues = phase === 'reviewing'

  return (
    <div id="preview-grid">
      {!hasContent && (
        <div className="empty-state">
          <div className="large-icon">&#x25A1;</div>
          <div className="msg">等待指令</div>
          <div className="sub">在左侧输入 PPT 主题开始生成</div>
        </div>
      )}

      {hasContent && outline.pages.map(p => (
        <SlideCard
          key={p.index}
          index={p.index}
          svg={slides[p.index]}
          onClick={() => slides[p.index] && onSlideClick(p.index)}
          issueSeverity={showIssues ? issueMap.get(p.index) : undefined}
        />
      ))}
    </div>
  )
}
