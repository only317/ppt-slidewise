interface Props {
  index: number
  svg?: string
  onClick: () => void
}

export function SlideCard({ index, svg, onClick }: Props) {
  if (!svg) {
    return (
      <div className="slide-card skeleton">
        <div className="skel-inner"><div className="skel-pulse" /></div>
        <div className="page-num">第 {index} 页</div>
      </div>
    )
  }

  return (
    <div className="slide-card" onClick={onClick}>
      <div dangerouslySetInnerHTML={{ __html: svg }} />
      <div className="page-num">第 {index} 页</div>
    </div>
  )
}
