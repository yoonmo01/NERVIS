export function isWakePhrase(text: string) {
  return /hey(?:nervis|nervous)/i.test(text.replace(/[^a-z]/gi, ''))
}

// Two short loud bursts, with a quiet gap; not a general sound classifier.
export class DoubleClap {
  private floor = 0.005
  private burst = -1
  private lastLoud = 0
  private previous = -Infinity
  feed(rms: number, peak: number, time: number) {
    const loud = rms > Math.max(0.035, this.floor * 5) && peak > 0.12
    if (loud) {
      if (this.burst < 0) this.burst = time
      this.lastLoud = time
    } else {
      this.floor = this.floor * 0.99 + Math.min(rms, 0.02) * 0.01
      if (this.burst >= 0 && time - this.lastLoud > 60) {
        const start = this.burst, duration = this.lastLoud - start
        this.burst = -1
        if (duration > 140) { this.previous = -Infinity; return false }
        const gap = start - this.previous
        this.previous = start
        if (gap >= 180 && gap <= 850) { this.previous = -Infinity; return true }
      }
    }
    return false
  }
}
