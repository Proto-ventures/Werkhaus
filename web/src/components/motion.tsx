import { useEffect, useRef, useState } from 'react'
import { useReducedMotion } from 'motion/react'

/**
 * Cycles example ideas through an empty input, typed out.
 *
 * It fills the box before anyone has typed and it shows what a usable answer
 * looks like, which is the job a static placeholder does badly.
 */
export function useTypedPlaceholder(phrases: string[], paused: boolean): string {
  const reduced = useReducedMotion()
  const [text, setText] = useState('')
  const index = useRef(0)
  const cursor = useRef(0)
  const erasing = useRef(false)

  useEffect(() => {
    if (paused || reduced) {
      setText(phrases[0])
      return
    }
    let timer: ReturnType<typeof setTimeout>

    const tick = () => {
      const phrase = phrases[index.current % phrases.length]
      if (!erasing.current) {
        cursor.current += 1
        setText(phrase.slice(0, cursor.current))
        if (cursor.current >= phrase.length) {
          erasing.current = true
          timer = setTimeout(tick, 2600)
          return
        }
        // Uneven keystrokes; a metronome reads as a machine typing.
        timer = setTimeout(tick, 18 + Math.random() * 34)
      } else {
        cursor.current -= 6
        if (cursor.current <= 0) {
          cursor.current = 0
          erasing.current = false
          index.current += 1
          setText('')
          timer = setTimeout(tick, 400)
          return
        }
        setText(phrase.slice(0, cursor.current))
        timer = setTimeout(tick, 16)
      }
    }

    timer = setTimeout(tick, 700)
    return () => clearTimeout(timer)
  }, [phrases, paused, reduced])

  return text
}

/** Counts to a number when it scrolls into view. Used once, on the verdict. */
export function CountUp({ to, className }: { to: number; className?: string }) {
  const reduced = useReducedMotion()
  const ref = useRef<HTMLSpanElement>(null)
  const [value, setValue] = useState(() => to)

  useEffect(() => {
    if (reduced || !ref.current) return
    setValue(0)
    const observer = new IntersectionObserver(([entry]) => {
      if (!entry.isIntersecting) return
      observer.disconnect()
      const started = performance.now()
      const duration = 900
      const frame = (now: number) => {
        const t = Math.min(1, (now - started) / duration)
        // ease-out, so it decelerates into the final number
        setValue(Math.round(to * (1 - (1 - t) ** 3)))
        if (t < 1) requestAnimationFrame(frame)
      }
      requestAnimationFrame(frame)
    })
    observer.observe(ref.current)
    return () => observer.disconnect()
  }, [to, reduced])

  return (
    <span ref={ref} className={className}>
      {value}%
    </span>
  )
}
