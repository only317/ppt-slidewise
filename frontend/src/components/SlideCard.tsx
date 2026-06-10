interface Props {
  index: number
  svg?: string
  onClick: () => void
  issueSeverity?: string  // 'error' | 'warning' | 'suggestion' | undefined
}

const SEV_BADGE: Record<string, { label: string; cls: string }> = {
  error:      { label: '严重', cls: 'badge-error' },
  warning:    { label: '警告', cls: 'badge-warn' },
  suggestion: { label: '建议', cls: 'badge-sugg' },
}

export function SlideCard({ index, svg, onClick, issueSeverity }: Props) {
  if (!svg) {
    return (
      <div className="slide-card skeleton">
        <div className="skel-inner"><div className="skel-pulse" /></div>
        <div className="page-num">第{index}页</div>
      </div>
    )
  }

  const badge = issueSeverity ? SEV_BADGE[issueSeverity] : null

  return (
    <div className={`slide-card${issueSeverity ? ' has-issue' : ''}`} onClick={onClick}>
      <div dangerouslySetInnerHTML={{ __html: svg }} />
      <div className="page-num">第{index}页</div>
      {badge && (
        <div className={`issue-badge ${badge.cls}`}>{badge.label}</div>
      )}
    </div>
  )
}
