/** Longest-match IPA → transcript. Keep in sync with api/app/rewriter.py. */

export function tokenizeIpa(ipa) {
  return ipa.replaceAll(".", " ").replaceAll("-", " ").split(/\s+/).filter(Boolean);
}

function normalize(text, form) {
  return (text || "").normalize(form || "NFC");
}

function compileRules(transcriptMap) {
  const rules = transcriptMap.rules || [];
  return [...rules]
    .map((rule) => [rule.ipa, rule.out ?? ""])
    .sort((a, b) => b[0].length - a[0].length);
}

function greedy(text, compiled, unknown) {
  let i = 0;
  const chunks = [];
  while (i < text.length) {
    let matched = false;
    for (const [src, dst] of compiled) {
      if (text.startsWith(src, i)) {
        chunks.push(dst);
        i += src.length;
        matched = true;
        break;
      }
    }
    if (!matched) {
      chunks.push(unknown != null ? unknown : text[i]);
      i += 1;
    }
  }
  return chunks.join("");
}

export function applyMap(ipa, transcriptMap, aliases = {}) {
  const form = transcriptMap.normalize || "NFC";
  const separator = transcriptMap.separator ?? "";
  const unknown = Object.hasOwn(transcriptMap, "unknown") ? transcriptMap.unknown : undefined;
  const compiled = compileRules(transcriptMap);
  const lookup = Object.fromEntries(compiled);
  const fold = transcriptMap.id === "ipa" ? {} : aliases;
  const tokens = tokenizeIpa(normalize(ipa, form));
  if (!tokens.length) {
    return greedy([...ipa].join("").replace(/\s+/g, ""), compiled, unknown);
  }
  const out = tokens.map((token) => {
    const folded = Object.hasOwn(fold, token) ? fold[token] : token;
    if (Object.hasOwn(lookup, folded)) return lookup[folded];
    if (unknown !== undefined) return unknown;
    return folded;
  });
  return normalize(out.join(separator), form);
}
