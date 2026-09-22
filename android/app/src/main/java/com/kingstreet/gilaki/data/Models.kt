package com.kingstreet.gilaki.data

import com.kingstreet.gilaki.rewriter.MapRule
import com.kingstreet.gilaki.rewriter.TranscriptMap
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
data class HealthResponse(
    val ok: Boolean = false,
    val status: String? = null,
    val backend: String? = null,
    val version: String? = null,
)

@Serializable
data class PresetSummary(
    val id: String,
    val name: String? = null,
    val script: String? = null,
    val direction: String = "ltr",
    val lossy: Boolean = false,
    val description: String? = null,
)

@Serializable
data class PhonologyResponse(
    val ok: Boolean = false,
    val inventory: InventoryWire = InventoryWire(),
)

@Serializable
data class InventoryWire(
    val aliases: Map<String, String> = emptyMap(),
)

@Serializable
data class PresetsResponse(
    val ok: Boolean = false,
    val presets: List<PresetSummary> = emptyList(),
)

@Serializable
data class WireRule(
    val ipa: String,
    val out: String = "",
)

@Serializable
data class WireMap(
    val id: String? = null,
    val name: String? = null,
    val script: String? = null,
    val direction: String = "ltr",
    val lossy: Boolean = false,
    val normalize: String = "NFC",
    val separator: String = "",
    val unknown: String? = null,
    val rules: List<WireRule> = emptyList(),
)

@Serializable
data class PresetDetailResponse(
    val ok: Boolean = false,
    val preset: WireMap? = null,
)

@Serializable
data class RecognizeResponse(
    val ok: Boolean = false,
    val ipa: String? = null,
    val backend: String? = null,
    @SerialName("mapped_text") val mappedText: String? = null,
)

fun WireMap.toTranscriptMap(): TranscriptMap = TranscriptMap(
    id = id,
    name = name,
    script = script,
    direction = direction,
    lossy = lossy,
    normalize = normalize,
    separator = separator,
    unknown = unknown,
    rules = rules.map { MapRule(it.ipa, it.out) },
)
