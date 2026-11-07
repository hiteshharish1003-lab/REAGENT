import { motion, useScroll, useTransform } from 'framer-motion'
import { useEffect, useRef } from 'react'
import { ArchiveDemo, InquiryDemo } from '../components/EngineDemos'
import HeroPreview from '../components/HeroPreview'
import { CountUp, Reveal, RiseWords } from '../components/Reveal'
import Tilt from '../components/Tilt'
import { hrefFor } from '../router'

const TICKER = ['Passage retrieval', 'Claim-level verification', 'Source conflicts surfaced', 'Plan approval', 'Cited reports', 'Evaluated against a baseline', 'Dark and light']

const STEPS = [
  { n: '01', t: 'Gather only what is relevant', d: 'Archive ranks passages from your own documents. Inquiry plans a set of questions you approve, then searches the web for each one. Nothing is written yet.' },
  { n: '02', t: 'Write strictly from the evidence', d: 'The writer receives the passages and nothing else. Every sentence makes one claim and names the sources it relies on.' },
  { n: '03', t: 'Judge every sentence', d: 'A separate pass checks each claim against its cited passage and returns one of three verdicts: supported, contradicted, or unsupported.' },
  { n: '04', t: 'Correct, or remove', d: 'A wrong figure is fixed from its source. A claim nothing supports is trimmed or removed. You can still see what changed and why.' },
]

const PRINCIPLES = [
  { n: 1, t: 'Claim per sentence', d: 'Sentences are the unit of checking, so a single weak claim cannot hide inside a good paragraph.' },
  { n: 3, t: 'Verdicts, no vague scores', d: 'Supported, contradicted or unsupported, each with the passage it rests on.' },
  { n: 0, t: 'Servers to manage', d: 'One local database. Documents are stored on this machine, and only the passages you ask about are sent to a model.' },
  { n: 2, t: 'Architectures measured', d: 'A single-agent baseline and the multi-agent pipeline are evaluated side by side, honestly.' },
]

export default function Landing({ onOpen }: { onOpen: (r: 'archive' | 'inquiry') => void }) {
  const stepsRef = useRef<HTMLDivElement>(null)
  const { scrollYProgress } = useScroll({ target: stepsRef, offset: ['start 62%', 'end 72%'] })
  const scaleY = useTransform(scrollYProgress, [0, 1], [0, 1])

  // Deep links such as #engines or #method scroll to that section once the page has mounted.
  useEffect(() => {
    const id = window.location.hash.replace(/^#\/?/, '')
    if (!id) return
    const t = setTimeout(() => document.getElementById(id)?.scrollIntoView({ behavior: 'instant' }), 350)
    return () => clearTimeout(t)
  }, [])

  return (
    <>
      <section className="hero">
        <div className="container hero-grid">
          <div>
            <motion.div className="kicker" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.7 }}>
              <i /> Documents and research, verified
            </motion.div>
            <h1 className="display"><RiseWords text="Answers that [[show their work.]]" delay={0.15} /></h1>
            <motion.p className="lede" initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.8, delay: 0.7 }}>
              REAGENT gives you two engines. Archive answers questions from your own documents. Inquiry researches the open web and writes a cited report. Both check every sentence against its source before you read it.
            </motion.p>
            <motion.div className="cta-row" initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.8, delay: 0.85 }}>
              <a className="btn btn-solid btn-lg" href={hrefFor('archive')}>Open Archive</a>
              <a className="btn btn-lg" href={hrefFor('inquiry')}>Start an inquiry</a>
            </motion.div>
          </div>
          <motion.div initial={{ opacity: 0, y: 30, rotateX: 6 }} animate={{ opacity: 1, y: 0, rotateX: 0 }} transition={{ duration: 1, delay: 0.5, ease: [0.22, 1, 0.36, 1] }}>
            <HeroPreview />
          </motion.div>
        </div>
      </section>

      <div className="ticker" aria-hidden>
        <div className="ticker-track">
          {[...TICKER, ...TICKER].map((t, i) => <span key={i}>{t}</span>)}
        </div>
      </div>

      <section className="section" id="engines">
        <div className="container">
          <Reveal className="section-head">
            <span className="label">The engines</span>
            <h2 className="h2">Two ways in. <em>One standard of evidence.</em></h2>
            <p>Choose the engine that fits the question. Each has its own workspace, built around how that work is actually done.</p>
          </Reveal>
          <div className="engines">
            <Reveal>
              <Tilt className="engine-card" label="Open Archive" onOpen={() => onOpen('archive')}>
                <div className="engine-top"><span className="label">01 · Document retrieval</span></div>
                <div className="engine-name">Archive</div>
                <p>Upload reports, papers and notes. Ask in plain language and get an answer built only from your pages, with the passage behind every sentence.</p>
                <ArchiveDemo />
                <span className="engine-open">Open Archive <span className="arrow-line" /></span>
              </Tilt>
            </Reveal>
            <Reveal delay={0.12}>
              <Tilt className="engine-card" label="Open Inquiry" onOpen={() => onOpen('inquiry')}>
                <div className="engine-top"><span className="label">02 · Multi-agent research</span></div>
                <div className="engine-name">Inquiry</div>
                <p>Pose a topic. A planner, researcher, analyst, writer and fact-checker work in sequence, you approve the plan, and conflicts between sources are surfaced.</p>
                <InquiryDemo />
                <span className="engine-open">Start an inquiry <span className="arrow-line" /></span>
              </Tilt>
            </Reveal>
          </div>
        </div>
      </section>

      <section className="section" id="method" style={{ paddingTop: 0 }}>
        <div className="container method">
          <div className="method-sticky">
            <Reveal>
              <span className="label">Method</span>
              <h2 className="h2">How an answer is <em>earned.</em></h2>
              <p className="muted" style={{ marginTop: 20, maxWidth: 380, fontSize: 16 }}>The same four steps sit behind both engines. The checking is what separates a plausible answer from a verified one.</p>
            </Reveal>
          </div>
          <div className="steps" ref={stepsRef}>
            <div className="steps-rail"><motion.i style={{ scaleY }} /></div>
            {STEPS.map((s) => (
              <Reveal key={s.n} className="step">
                <span className="num">{s.n}</span>
                <h3>{s.t}</h3>
                <p>{s.d}</p>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      <section className="section" id="principles" style={{ paddingTop: 0 }}>
        <div className="container">
          <Reveal className="section-head">
            <span className="label">Principles</span>
            <h2 className="h2">Built to be <em>checked.</em></h2>
          </Reveal>
          <Reveal>
            <div className="principles">
              {PRINCIPLES.map((p) => (
                <div className="principle" key={p.t}>
                  <CountUp to={p.n} />
                  <h4>{p.t}</h4>
                  <p>{p.d}</p>
                </div>
              ))}
            </div>
          </Reveal>
        </div>
      </section>

      <section className="section closing" style={{ paddingTop: 0 }}>
        <div className="container">
          <Reveal>
            <h2 className="h2">Bring a question, <em>or a stack of documents.</em></h2>
            <div className="cta-row">
              <a className="btn btn-solid btn-lg" href={hrefFor('archive')}>Open Archive</a>
              <a className="btn btn-lg" href={hrefFor('inquiry')}>Start an inquiry</a>
            </div>
          </Reveal>
        </div>
      </section>

      <footer className="footer">
        <div className="container"><span>REAGENT</span><span>Runs locally. Documents stay on this machine.</span></div>
      </footer>
    </>
  )
}
