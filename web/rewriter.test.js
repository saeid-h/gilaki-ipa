import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { describe, it } from "node:test";
import { fileURLToPath } from "node:url";

import { applyMap } from "./rewriter.js";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");

function preset(id) {
  return JSON.parse(readFileSync(join(root, "schemas", "presets", `${id}.json`), "utf8"));
}

describe("shared rewriter cases", () => {
  it("maps tʃ ə to Varg چٚ, not t + ʃ", () => {
    assert.equal(applyMap("tʃ ə", preset("varg-perso-arabic")), "چٚ");
  });

  it("keeps schwa on Varg and academic-latin", () => {
    const ipa = "m ə ʃ ə n ɒ";
    assert.match(applyMap(ipa, preset("varg-perso-arabic")), /ٚ/);
    assert.match(applyMap(ipa, preset("academic-latin")), /ə/);
    assert.equal(applyMap(ipa, preset("academic-latin")), "məšənå");
  });

  it("passes unknown phones through", () => {
    assert.equal(applyMap("q ə", preset("academic-latin")), "qə");
  });

  it("keeps IPA phones on the ipa preset", () => {
    assert.equal(applyMap("m ə ʃ ə n ɒ", preset("ipa")), "m ə ʃ ə n ɒ");
  });

  it("folds a tie bar while mapping, and leaves it on the IPA preset", () => {
    const aliases = JSON.parse(readFileSync(join(root, "schemas", "gilaki_inventory.json"), "utf8")).aliases;
    assert.equal(applyMap("t͡ʃ ə", preset("varg-perso-arabic"), aliases), "چٚ");
    assert.equal(applyMap("t͡ʃ æ", preset("ipa"), aliases), "t͡ʃ æ");
  });

  it("folds learned diacritics and drops an empty alias, except on IPA", () => {
    const aliases = JSON.parse(readFileSync(join(root, "schemas", "gilaki_inventory.json"), "utf8")).aliases;
    assert.equal(applyMap("s̪", preset("varg-perso-arabic"), aliases), "س");
    assert.equal(applyMap("b̥", preset("varg-perso-arabic"), aliases), "ب");
    const drop = { ...aliases, "ʌ": "" };
    assert.equal(applyMap("ʌ m", preset("varg-perso-arabic"), drop), "م");
    assert.equal(applyMap("ʌ m", preset("ipa"), drop), "ʌ m");
  });

  it("lossy-persian may collapse ə", () => {
    const mapped = applyMap("m ə", preset("lossy-persian"));
    assert.ok(!mapped.includes("ə"));
    assert.ok(!mapped.includes("ٚ"));
  });
});
