export function exportPaths(stem) {
  const base = String(stem || "take").replace(/\.wav$/i, "");
  return { wav: `${base}.wav`, ipa: `${base}.ipa.txt` };
}

export function ipaFileBody(ipa) {
  return `${String(ipa || "").trim()}\n`;
}

function writeUtf8(text, offset, view) {
  for (let i = 0; i < text.length; i += 1) {
    view.setUint8(offset + i, text.charCodeAt(i));
  }
}

/** 16-bit PCM mono WAV. Used so exports match the server ffmpeg grain. */
export function pcmToWav(pcm, sampleRate = 16000) {
  const data = pcm instanceof Int16Array ? pcm : Int16Array.from(pcm);
  const header = 44;
  const bytes = data.byteLength;
  const buffer = new ArrayBuffer(header + bytes);
  const view = new DataView(buffer);
  writeUtf8("RIFF", 0, view);
  view.setUint32(4, 36 + bytes, true);
  writeUtf8("WAVE", 8, view);
  writeUtf8("fmt ", 12, view);
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  writeUtf8("data", 36, view);
  view.setUint32(40, bytes, true);
  new Uint8Array(buffer, header).set(new Uint8Array(data.buffer, data.byteOffset, bytes));
  return new Blob([buffer], { type: "audio/wav" });
}

export async function blobToWav(blob, sampleRate = 16000) {
  if (typeof AudioContext === "undefined") {
    return blob;
  }
  const ctx = new AudioContext({ sampleRate });
  try {
    const decoded = await ctx.decodeAudioData(await blob.arrayBuffer());
    const length = decoded.length;
    const pcm = new Int16Array(length);
    const src = decoded.numberOfChannels ? decoded.getChannelData(0) : new Float32Array(length);
    for (let i = 0; i < length; i += 1) {
      const s = Math.max(-1, Math.min(1, src[i] || 0));
      pcm[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
    }
    return pcmToWav(pcm, decoded.sampleRate || sampleRate);
  } finally {
    await ctx.close().catch(() => {});
  }
}
