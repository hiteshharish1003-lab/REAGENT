import { motion, useScroll, useTransform } from 'framer-motion'

/** Ambient background: slow gradient fields, a faint grid and film grain. Pure CSS animation plus one scroll parallax. */
export default function Backdrop({ calm }: { calm: boolean }) {
  const { scrollY } = useScroll()
  const y = useTransform(scrollY, [0, 1600], [0, -180])
  return (
    <div className={`backdrop ${calm ? 'calm' : ''}`} aria-hidden>
      <motion.div style={{ y }} className="backdrop-parallax">
        <i className="blob b1" />
        <i className="blob b2" />
        <i className="blob b3" />
      </motion.div>
      <div className="lines" />
      <div className="grain" />
    </div>
  )
}
