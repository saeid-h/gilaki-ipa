import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { exportPaths, ipaFileBody, pcmToWav } from "./export.js";

describe("export pair shape", () => {
  it("writes wav and ipa.txt side by side", () => {
    assert.deepEqual(exportPaths("clip-1"), { wav: "clip-1.wav", ipa: "clip-1.ipa.txt" });
    assert.equal(ipaFileBody("m ə ʃ"), "m ə ʃ\n");
  });

  it("encodes a PCM wav header", async () => {
    const wav = pcmToWav(new Int16Array([0, 1, -1]), 16000);
    const bytes = new Uint8Array(await wav.arrayBuffer());
    assert.equal(new TextDecoder().decode(bytes.slice(0, 4)), "RIFF");
    assert.equal(new TextDecoder().decode(bytes.slice(8, 12)), "WAVE");
    assert.equal(bytes.byteLength, 44 + 6);
  });
});
