import { AnimatePresence, motion } from 'framer-motion'
import type { Source } from '../types'

function highlight(content: string, passage: string) {
  const i = passage ? content.indexOf(passage) : -1
  if (i < 0) return <>{content}</>
  return (
    <>
      {content.slice(0, i)}
      <mark>{passage}</mark>
      {content.slice(i + passage.length)}
    </>
  )
}

interface Props {
  source: Source | null
  passage: string
  onClose: () => void
}

export default function SourceDrawer({ source, passage, onClose }: Props) {
  const isDoc = !!source && source.url.startsWith('doc:')
  return (
    <AnimatePresence>
      {source && (
        <>
          <motion.div className="scrim" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={onClose} />
          <motion.aside className="drawer" initial={{ x: 420 }} animate={{ x: 0 }} exit={{ x: 420 }} transition={{ type: 'spring', stiffness: 260, damping: 30 }}>
            <div className="drawer-head">
              <div>
                <div className="drawer-domain">{isDoc ? 'Passage from' : ''} {source.domain}</div>
                <h3>{source.title}</h3>
              </div>
              <button className="btn btn-quiet" onClick={onClose}>Close</button>
            </div>
            {isDoc ? (
              <div className="quality"><span>{source.quality_reason}</span></div>
            ) : (
              <div className="quality">
                <div className="quality-bar"><motion.i initial={{ width: 0 }} animate={{ width: `${source.quality * 100}%` }} /></div>
                <span>{source.quality_reason} · trust {Math.round(source.quality * 100)}</span>
              </div>
            )}
            <div className="drawer-body">{highlight(source.content, passage)}</div>
            {!isDoc && <a className="btn" href={source.url} target="_blank" rel="noreferrer">Open original</a>}
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  )
}
