import { useState } from 'react'
import { SlideCard } from './SlideCard'

interface Props {
  outline: { pages: { index: number }[] } | null
  slides: Record<number, string>
  onSlideClick: (index: number) => void
}

export function SlideGrid({ outline, slides, onSlideClick }: Props) {
  const hasContent = outline && outline.pages.length > 0

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
        />
      ))}
    </div>
  )
}
