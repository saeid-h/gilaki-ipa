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

fun applyMap(ipa: String, transcriptMap: TranscriptMap): String {
    val form = transcriptMap.normalize.ifBlank { "NFC" }
    val compiled = transcriptMap.rules
        .map { it.ipa to it.out }
        .sortedByDescending { it.first.length }
    val lookup = compiled.toMap()
    val tokens = tokenizeIpa(normalize(ipa, form))
    if (tokens.isEmpty()) {
        return greedy(ipa.split(Regex("\\s+")).joinToString(""), compiled, transcriptMap.unknown)
    }
    val out = tokens.map { token ->
        lookup[token] ?: transcriptMap.unknown ?: token
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
