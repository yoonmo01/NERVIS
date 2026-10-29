class Microphone extends AudioWorkletProcessor {
  process(inputs) {
    const samples = inputs[0]?.[0]
    if (samples?.length) {
      const pcm = new Int16Array(samples.length)
      for (let i = 0; i < samples.length; i++) {
        const sample = Math.max(-1, Math.min(1, samples[i]))
        pcm[i] = Math.round(sample * (sample < 0 ? 32768 : 32767))
      }
      this.port.postMessage(pcm.buffer, [pcm.buffer])
    }
    return true
  }
}
registerProcessor('nervis-microphone', Microphone)
