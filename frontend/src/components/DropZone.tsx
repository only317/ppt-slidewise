interface Props {
  active: boolean
  onFiles: (files: FileList) => void
}

export function DropZone({ active }: Props) {
  if (!active) return null
  return (
    <div id="drop-zone" className="active">
      <div className="dz-text">释放文件以添加</div>
      <div className="dz-sub">支持 PDF · DOCX · Markdown</div>
    </div>
  )
}
