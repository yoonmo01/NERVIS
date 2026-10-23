export const INTRO = { dock: 1200, core: 2600, ready: 4300 }
export type IntroStage = 'title' | 'dock' | 'core' | 'ready'

export function introStage(elapsed: number, reduced = false): IntroStage {
  if (reduced || elapsed >= INTRO.ready) return 'ready'
  if (elapsed >= INTRO.core) return 'core'
  if (elapsed >= INTRO.dock) return 'dock'
  return 'title'
}

export function makeCoreGeometry() {
  const shell: number[] = [], inner: number[] = [], panels: number[] = [], particles: number[] = []
  const point = (r: number, p: number, t: number) => [r * Math.sin(p) * Math.cos(t), r * Math.cos(p), r * Math.sin(p) * Math.sin(t)]
  const segment = (target: number[], a: number[], b: number[]) => target.push(...a, ...b)
  for (let row = 0; row < 17; row++) {
    const phi = 0.2 + row * (Math.PI - 0.4) / 16
    for (let section = 0; section < 14; section++) {
      const first = section * Math.PI / 7 + (row % 2) * 0.16
      const width = 0.19 + ((section + row) % 3) * 0.06
      const radius = 1.58 + Math.sin(row * 2) * 0.035
      for (let step = 0; step < 8; step++) {
        const t = first + step * width / 8, next = t + width / 8
        segment(shell, point(1.73, phi, t), point(1.73, phi, next))
        if ((row + section) % 4 === 0) continue
        const a = point(radius, phi, t), b = point(radius, phi, next)
        const c = point(radius, phi + 0.075, t), d = point(radius, phi + 0.075, next)
        panels.push(...a, ...b, ...c, ...b, ...d, ...c)
      }
      segment(shell, point(1.7, phi, first), point(1.84, phi, first))
    }
  }
  for (let column = 0; column < 9; column++) {
    const theta = column * Math.PI * 2 / 9
    for (let step = 0; step < 48; step++) {
      if (step % 8 < 3) continue
      const phi = 0.2 + step * (Math.PI - 0.4) / 48
      segment(shell, point(1.77, phi, theta), point(1.77, phi + 0.04, theta))
    }
  }
  for (let ring = 0; ring < 7; ring++) {
    const radius = 0.52 + ring * 0.145, tilt = ring * 0.24
    const circle = (t: number) => [Math.cos(t) * radius, Math.sin(t) * radius * Math.cos(tilt), Math.sin(t) * radius * Math.sin(tilt)]
    for (let step = 0; step < 120; step++) {
      if ((step + ring * 7) % 30 > 19) continue
      segment(inner, circle(step * Math.PI / 60), circle((step + 1) * Math.PI / 60))
      if (step % 5 === 0) {
        const a = circle(step * Math.PI / 60)
        segment(inner, a, a.map(v => v * 1.045))
      }
    }
  }
  let seed = 6043
  const random = () => { seed = (seed * 1664525 + 1013904223) >>> 0; return seed / 4294967296 }
  for (let i = 0; i < 2800; i++) {
    const radius = i < 2100 ? 1.8 + random() * 0.18 : 0.45 + random() * 0.95
    particles.push(...point(radius, Math.acos(2 * random() - 1), random() * Math.PI * 2))
  }
  const glow = new Uint8Array(64 * 64 * 4)
  for (let y = 0; y < 64; y++) for (let x = 0; x < 64; x++) {
    const i = (y * 64 + x) * 4
    const radius = Math.hypot((x - 31.5) / 32, (y - 31.5) / 32)
    glow.set([255, 255, 255, Math.round(255 * Math.max(0, 1 - radius) ** 2)], i)
  }
  return { shell: new Float32Array(shell), inner: new Float32Array(inner), panels: new Float32Array(panels), particles: new Float32Array(particles), glow }
}

export type CoreState = 'standby' | 'processing' | 'analyzing' | 'error' | 'paused' | 'preview'
export const coreStateColors: Record<CoreState, string> = { standby: '#68c9ff', processing: '#ffb05f', analyzing: '#61f0de', error: '#ff626e', paused: '#7193af', preview: '#68c9ff' }

export function coreMotion(elapsed: number, level: number, reduced: boolean, state: CoreState = 'standby') {
  const t = reduced || !Number.isFinite(elapsed) ? 0 : elapsed
  const amplitude = reduced || !Number.isFinite(level) ? 0 : Math.max(0, Math.min(1, level))
  const pulse = reduced ? 0 : state === 'error' ? (1 + Math.sin(t * 1.8)) * .04 : state === 'processing' ? (1 + Math.sin(t * 3)) * .025 : 0
  return {
    shellY: 0.3 + t * 0.18, innerY: 0.2 - t * 0.34, bandZ: 0.4 + t * 0.24,
    scale: 1 + amplitude * 0.065 + Math.sin(t * 1.1) * 0.008 + pulse,
    glow: 0.65 + amplitude * 0.85 + pulse * 3, panels: 0.16 + amplitude * 0.16,
    dust: 0.62 + amplitude * 0.3,
  }
}

export type ComposerPanel = 'text' | 'voice' | null
export function toggleComposer(current: ComposerPanel, target: 'text' | 'voice', view: 'home' | 'analysis'): ComposerPanel {
  return current === target ? (view === 'home' ? 'text' : null) : target
}

export function maskOverlay(pixels: Uint8ClampedArray, colors: Map<number, number[]>) {
  if (pixels.length % 4) throw new Error('Invalid RGBA mask')
  const result = new Uint8ClampedArray(pixels.length)
  for (let i = 0; i < pixels.length; i += 4) {
    const color = colors.get(pixels[i])
    if (color) result.set([color[0], color[1], color[2], 145], i)
  }
  return result
}

export function wavePath(values: number[], extent = Math.max(3, ...values.map(Math.abs))) {
  if (!values.every(Number.isFinite)) throw new Error('Invalid signal values')
  if (!Number.isFinite(extent) || extent <= 0) throw new Error('Invalid signal scale')
  const width = 1000, height = 120
  return values.map((v, i) => `${i ? 'L' : 'M'}${(i * width / Math.max(1, values.length - 1)).toFixed(2)},${(height / 2 - v / extent * (height / 2 - 8)).toFixed(2)}`).join(' ')
}

export function audioLevel(samples: Float32Array) {
  if (!samples.length) return 0
  let energy = 0
  for (const v of samples) energy += v * v
  return Math.min(1, Math.sqrt(energy / samples.length) * 6)
}
