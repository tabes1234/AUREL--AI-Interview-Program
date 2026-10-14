/** 浏览器录音 → WAV 转换：解码为 PCM 后统一封装成 16-bit 单声道 WAV，
 * 让本地客观指标（时长/停顿）与各 ASR 提供方都能直接处理。 */

export class AudioEncodeError extends Error {}

export async function blobToWavFile(blob: Blob, name = 'recording.wav'): Promise<File> {
  const AudioCtx: typeof AudioContext | undefined =
    window.AudioContext ?? (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext
  if (!AudioCtx) throw new AudioEncodeError('当前浏览器不支持音频解码')

  const ctx = new AudioCtx()
  try {
    const decoded = await ctx.decodeAudioData(await blob.arrayBuffer())
    const wav = encodeWavPcm16(decoded)
    return new File([wav], name, { type: 'audio/wav' })
  } catch {
    throw new AudioEncodeError('无法解码录音数据')
  } finally {
    void ctx.close()
  }
}

function encodeWavPcm16(buffer: AudioBuffer): ArrayBuffer {
  const channels = buffer.numberOfChannels
  const length = buffer.length
  const mono = new Float32Array(length)
  for (let ch = 0; ch < channels; ch += 1) {
    const data = buffer.getChannelData(ch)
    for (let i = 0; i < length; i += 1) mono[i] += data[i] / channels
  }

  const bytesPerSample = 2
  const dataSize = length * bytesPerSample
  const out = new ArrayBuffer(44 + dataSize)
  const view = new DataView(out)

  writeAscii(view, 0, 'RIFF')
  view.setUint32(4, 36 + dataSize, true)
  writeAscii(view, 8, 'WAVE')
  writeAscii(view, 12, 'fmt ')
  view.setUint32(16, 16, true)
  view.setUint16(20, 1, true) // PCM
  view.setUint16(22, 1, true) // 单声道
  view.setUint32(24, buffer.sampleRate, true)
  view.setUint32(28, buffer.sampleRate * bytesPerSample, true)
  view.setUint16(32, bytesPerSample, true)
  view.setUint16(34, 16, true)
  writeAscii(view, 36, 'data')
  view.setUint32(40, dataSize, true)

  let offset = 44
  for (let i = 0; i < length; i += 1) {
    const clamped = Math.max(-1, Math.min(1, mono[i]))
    view.setInt16(offset, clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff, true)
    offset += bytesPerSample
  }
  return out
}

function writeAscii(view: DataView, offset: number, text: string): void {
  for (let i = 0; i < text.length; i += 1) view.setUint8(offset + i, text.charCodeAt(i))
}
