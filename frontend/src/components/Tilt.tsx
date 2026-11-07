import { motion, useMotionValue, useReducedMotion, useSpring, useTransform } from 'framer-motion'
import { useRef, type KeyboardEvent, type ReactNode } from 'react'

interface Props {
  children: ReactNode
  className?: string
  label: string
  onOpen: () => void
}

/** Card with a cursor-following spotlight and a restrained 3D tilt. Keyboard operable. */
export default function Tilt({ children, className = '', label, onOpen }: Props) {
  const ref = useRef<HTMLDivElement>(null)
  const reduce = useReducedMotion()
  const px = useMotionValue(0.5)
  const py = useMotionValue(0.5)
  const spring = { stiffness: 180, damping: 22, mass: 0.5 }
  const rotateX = useSpring(useTransform(py, [0, 1], [3.2, -3.2]), spring)
  const rotateY = useSpring(useTransform(px, [0, 1], [-3.8, 3.8]), spring)

  const move = (e: React.PointerEvent<HTMLDivElement>) => {
    const el = ref.current
    if (!el || e.pointerType === 'touch') return
    const r = el.getBoundingClientRect()
    const x = (e.clientX - r.left) / r.width
    const y = (e.clientY - r.top) / r.height
    px.set(x); py.set(y)
    el.style.setProperty('--mx', `${x * 100}%`)
    el.style.setProperty('--my', `${y * 100}%`)
  }
  const leave = () => { px.set(0.5); py.set(0.5) }
  const key = (e: KeyboardEvent) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onOpen() } }

  return (
    <motion.div
      ref={ref}
      role="link"
      tabIndex={0}
      aria-label={label}
      className={className}
      style={reduce ? undefined : { rotateX, rotateY }}
      onPointerMove={move}
      onPointerLeave={leave}
      onClick={onOpen}
      onKeyDown={key}
      whileTap={{ scale: 0.995 }}
    >
      {children}
    </motion.div>
  )
}
