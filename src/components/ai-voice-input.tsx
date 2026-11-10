import { useEffect, useId, useRef, useState } from 'react'
import { Button } from '@/components/ui/button'
import workletUrl from './ai-pcm-worklet.js?url&no-inline'

type Recording = { context: AudioContext; stream: MediaStream; node?: AudioWorkletNode; chunks: Float32Array[]; samples: number; timer?: number }

// One canonical 16kHz mono PCM WAV. No compressed or remote media input.
export function pcmWav(chunks: Float32Array[], rate: number): string {
  const length = chunks.reduce((total, chunk) => total + chunk.length, 0)
  const input = new Float32Array(length)
  let offset = 0
  for (const chunk of chunks) { input.set(chunk, offset); offset += chunk.length }
  const count = Math.min(240000, Math.floor(length * 16000 / rate))
  if (count < 1600) throw new Error('VOICE_TOO_SHORT')
  const data = new Uint8Array(44 + count * 2)
  const view = new DataView(data.buffer)
  const label = (at: number, text: string) => [...text].forEach((char, i) => view.setUint8(at + i, char.charCodeAt(0)))
  label(0, 'RIFF'); view.setUint32(4, data.length - 8, true); label(8, 'WAVE'); label(12, 'fmt ')
  view.setUint32(16, 16, true); view.setUint16(20, 1, true); view.setUint16(22, 1, true)
  view.setUint32(24, 16000, true); view.setUint32(28, 32000, true); view.setUint16(32, 2, true); view.setUint16(34, 16, true)
  label(36, 'data'); view.setUint32(40, count * 2, true)
  for (let i = 0; i < count; i++) {
    // Average samples in the source interval to avoid point-sampling aliasing.
    const begin = Math.floor(i * rate / 16000), end = Math.max(begin + 1, Math.floor((i + 1) * rate / 16000))
    let sum = 0
    for (let j = begin; j < end; j++) sum += input[j] ?? 0
    const sample = Math.max(-1, Math.min(1, sum / (end - begin)))
    view.setInt16(44 + i * 2, Math.round(sample * (sample < 0 ? 32768 : 32767)), true)
  }
  let binary = ''
  for (let i = 0; i < data.length; i += 8192) binary += String.fromCharCode(...data.subarray(i, i + 8192))
  return btoa(binary)
}

export function AIVoiceInput({ disabled, disabledReason, onAudio, onRecording }: { disabled: boolean; disabledReason?: string; onAudio: (audio: string) => void; onRecording: (value: boolean) => void }) {
  const reasonId = useId()
  const [state, setState] = useState<'idle' | 'permission' | 'recording'>('idle')
  const [notice, setNotice] = useState('')
  const owned = useRef<Recording | null>(null)
  const generation = useRef(0)
  const mounted = useRef(true)
  const recordingCallback = useRef(onRecording)
  recordingCallback.current = onRecording
  function cleanup() {
    const value = owned.current
    owned.current = null
    if (value) {
      window.clearTimeout(value.timer)
      if (value.node) { value.node.port.onmessage = null; value.node.disconnect() }
      value.stream.getTracks().forEach(track => track.stop())
      void value.context.close().catch(() => {})
    }
    recordingCallback.current(false)
    return value
  }
  useEffect(() => {
    mounted.current = true
    // The counter deliberately invalidates an unresolved permission request.
    // oxlint-disable-next-line react-hooks/exhaustive-deps
    return () => { mounted.current = false; generation.current++; cleanup() }
  }, [])
  function stop(send: boolean) {
    generation.current++
    const value = cleanup()
    setState('idle')
    if (send && value) {
      try { onAudio(pcmWav(value.chunks, value.context.sampleRate)) }
      catch { setNotice('Запись слишком короткая. Повторите или введите запрос текстом.') }
    }
  }
  async function start() {
    if (disabled || owned.current || state !== 'idle') return
    const ticket = ++generation.current
    setState('permission'); setNotice(''); onRecording(true)
    let stream: MediaStream | null = null
    try {
      if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia || !window.AudioWorkletNode) throw new Error('UNSUPPORTED')
      stream = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true }, video: false })
      if (!mounted.current || generation.current !== ticket) { stream.getTracks().forEach(track => track.stop()); return }
      const context = new AudioContext()
      const value: Recording = { context, stream, chunks: [], samples: 0 }
      owned.current = value
      await context.audioWorklet.addModule(workletUrl)
      if (!mounted.current || generation.current !== ticket) return
      const node = new AudioWorkletNode(context, 'ai-pcm-recorder')
      value.node = node
      node.port.onmessage = (event: MessageEvent<Float32Array>) => {
        if (owned.current !== value || !(event.data instanceof Float32Array)) return
        value.samples += event.data.length
        if (value.samples <= context.sampleRate * 15) value.chunks.push(event.data)
        else stop(true)
      }
      const mute = context.createGain(); mute.gain.value = 0
      context.createMediaStreamSource(stream).connect(node); node.connect(mute); mute.connect(context.destination)
      await context.resume()
      if (!mounted.current || generation.current !== ticket) return
      value.timer = window.setTimeout(() => stop(true), 15000)
      setState('recording')
    } catch (error) {
      stream?.getTracks().forEach(track => track.stop())
      if (!mounted.current || generation.current !== ticket) return
      cleanup(); setState('idle')
      setNotice(error instanceof DOMException && error.name === 'NotAllowedError'
        ? 'Разрешите доступ к микрофону в браузере или введите запрос текстом.'
        : 'Микрофон недоступен. Введите запрос текстом.')
    }
  }
  return <div data-i18n-exempt>
    <p>Голос: до 15 секунд. Аудио обрабатывается на нашем сервере без сохранения. После остановки поиск начнётся автоматически.</p>
    {state === 'idle' ? <Button type="button" variant="outline" disabled={disabled} aria-describedby={disabled && disabledReason ? reasonId : undefined} onClick={() => void start()}>Надиктовать запрос</Button>
      : <><p role="status">{state === 'permission' ? 'Ожидаем доступ к микрофону…' : 'Идёт запись…'}</p>
        <Button type="button" disabled={state !== 'recording'} onClick={() => stop(true)}>Остановить и искать</Button>
        <Button type="button" variant="outline" onClick={() => stop(false)}>Отменить запись</Button></>}
    {disabled && disabledReason && state === 'idle' ? <p id={reasonId} role="status" data-voice-unavailable>{disabledReason}</p> : null}
    {notice ? <p role="alert">{notice}</p> : null}
  </div>
}
