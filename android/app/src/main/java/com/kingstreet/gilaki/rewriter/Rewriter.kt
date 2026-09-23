package com.kingstreet.gilaki.rewriter

import java.text.Normalizer

data class MapRule(val ipa: String, val out: String = "")

data class TranscriptMap(
    val id: String? = null,
    val name: String? = null,
    val script: String? = null,
    val direction: String = "ltr",
    val lossy: Boolean = false,
    val normalize: String = "NFC",
    val separator: String = "",
    val unknown: String? = null,
    val rules: List<MapRule> = emptyList(),
)

fun tokenizeIpa(ipa: String): List<String> =
    ipa.replace(".", " ").replace("-", " ").split(Regex("\\s+")).filter { it.isNotEmpty() }

data class Rewrite(val from: List<String>, val to: List<String>)

/** Longest `from` first; equal lengths keep list order; each rule scans left to right without overlap. */
fun applyRewrites(tokens: List<String>, rewrites: List<Rewrite>): List<String> {
    var current = tokens
    for (rule in rewrites.sortedByDescending { it.from.size }) {
        val n = rule.from.size
        val out = ArrayList<String>(current.size)
        var i = 0
        while (i < current.size) {
            if (i + n <= current.size && current.subList(i, i + n) == rule.from) {
                out.addAll(rule.to)
                i += n
            } else {
                out.add(current[i])
                i += 1
            }
        }
        current = out
    }
    return current
}

fun applyMap(
    ipa: String,
    transcriptMap: TranscriptMap,
    aliases: Map<String, String> = emptyMap(),
    rewrites: List<Rewrite> = emptyList(),
): String {
    val form = transcriptMap.normalize.ifBlank { "NFC" }
    val compiled = transcriptMap.rules
        .map { it.ipa to it.out }
        .sortedByDescending { it.first.length }
    val lookup = compiled.toMap()
    val literal = transcriptMap.id == "ipa"
    val fold = if (literal) emptyMap() else aliases
    val tokens = tokenizeIpa(normalize(ipa, form))
    if (tokens.isEmpty()) {
        return greedy(ipa.split(Regex("\\s+")).joinToString(""), compiled, transcriptMap.unknown)
    }
    val folded = tokens.map { fold[it] ?: it }.filter { it.isNotEmpty() }
    val out = applyRewrites(folded, if (literal) emptyList() else rewrites).map { phone ->
        lookup[phone] ?: transcriptMap.unknown ?: phone
    }
    return normalize(out.joinToString(transcriptMap.separator), form)
}

private fun greedy(
    text: String,
    compiled: List<Pair<String, String>>,
    unknown: String?,
): String {
    val chunks = StringBuilder()
    var i = 0
    while (i < text.length) {
        val match = compiled.firstOrNull { text.startsWith(it.first, i) }
        if (match != null) {
            chunks.append(match.second)
            i += match.first.length
        } else {
            chunks.append(unknown ?: text[i].toString())
            i += 1
        }
    }
    return chunks.toString()
}

private fun normalize(text: String, form: String): String {
    val n = when (form.uppercase()) {
        "NFD" -> Normalizer.Form.NFD
        "NFKC" -> Normalizer.Form.NFKC
        "NFKD" -> Normalizer.Form.NFKD
        else -> Normalizer.Form.NFC
    }
    return Normalizer.normalize(text, n)
}
