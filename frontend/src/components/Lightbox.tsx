interface Props {
  index: number | null
  slides: Record<number, string>
  slideKeys: number[]
  onClose: () => void
  onPrev: () => void
  onNext: () => void
}

export function Lightbox({ index, slides, slideKeys, onClose, onPrev, onNext }: Props) {
  if (index === null) return null
  const svg = slides[index]
  if (!svg) return null

  return (
    <div id="lightbox" className="active" onClick={onClose}>
      <div className="lb-header" onClick={e => e.stopPropagation()}>
        <span className="lb-title">第 {index} 页</span>
        <div className="lb-close" onClick={onClose}>&#x2715;</div>
      </div>
      <div className="lb-nav prev" onClick={e => { e.stopPropagation(); onPrev() }}>&#x2190;</div>
      <div className="lb-nav next" onClick={e => { e.stopPropagation(); onNext() }}>&#x2192;</div>
      <div id="lightbox-content" onClick={e => e.stopPropagation()}
        dangerouslySetInnerHTML={{ __html: svg }} />
      <div className="lb-counter">{index} / {slideKeys.length}</div>
    </div>
  )
}
