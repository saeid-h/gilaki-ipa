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

/** Longest `from` first; equal lengths keep file order; each rule scans left to right without overlap. */
export function applyRewrites(tokens, rewrites = []) {
  const ordered = rewrites
    .map((rule, index) => ({ rule, index }))
    .sort((a, b) => b.rule.from.length - a.rule.from.length || a.index - b.index)
    .map(({ rule }) => rule);
  for (const { from, to } of ordered) {
    const out = [];
    let i = 0;
    while (i < tokens.length) {
      if (from.every((phone, k) => tokens[i + k] === phone)) {
        out.push(...to);
        i += from.length;
      } else {
        out.push(tokens[i]);
        i += 1;
      }
    }
    tokens = out;
  }
  return tokens;
}

export function applyMap(ipa, transcriptMap, aliases = {}, rewrites = []) {
  const form = transcriptMap.normalize || "NFC";
  const separator = transcriptMap.separator ?? "";
  const unknown = Object.hasOwn(transcriptMap, "unknown") ? transcriptMap.unknown : undefined;
  const compiled = compileRules(transcriptMap);
  const lookup = Object.fromEntries(compiled);
  const literal = transcriptMap.id === "ipa";
  const fold = literal ? {} : aliases;
  const tokens = tokenizeIpa(normalize(ipa, form));
  if (!tokens.length) {
    return greedy([...ipa].join("").replace(/\s+/g, ""), compiled, unknown);
  }
  const folded = tokens.map((token) => (Object.hasOwn(fold, token) ? fold[token] : token)).filter(Boolean);
  const out = applyRewrites(folded, literal ? [] : rewrites).map((phone) => {
    if (Object.hasOwn(lookup, phone)) return lookup[phone];
    if (unknown !== undefined) return unknown;
    return phone;
  });
  return normalize(out.join(separator), form);
}
