package com.kingstreet.gilaki.rewriter

import com.kingstreet.gilaki.data.WireMap
import com.kingstreet.gilaki.data.toTranscriptMap
import java.io.File
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class RewriterTest {
    private val json = Json { ignoreUnknownKeys = true }

    @Test
    fun longestMatchAffricate() {
        assertEquals("چٚ", applyMap("tʃ ə", preset("varg-perso-arabic")))
    }

    @Test
    fun schwaKeptOnVargAndAcademicLatin() {
        val ipa = "m ə ʃ ə n ɒ"
        val varg = applyMap(ipa, preset("varg-perso-arabic"))
        val latin = applyMap(ipa, preset("academic-latin"))
        assertTrue(varg.contains("ٚ"))
        assertTrue(latin.contains("ə"))
        assertEquals("məšənå", latin)
        assertEquals("مٚشٚنآ", varg)
    }

    @Test
    fun unknownPhonePassesThrough() {
        assertEquals("qə", applyMap("q ə", preset("academic-latin")))
    }

    @Test
    fun ipaPresetKeepsPhones() {
        assertEquals("m ə ʃ ə n ɒ", applyMap("m ə ʃ ə n ɒ", preset("ipa")))
    }

    @Test
    fun tieBarFoldsDuringMapping() {
        val fold = inventoryAliases()
        assertEquals("چٚ", applyMap("t͡ʃ ə", preset("varg-perso-arabic"), fold))
        assertEquals("t͡ʃ æ", applyMap("t͡ʃ æ", preset("ipa"), fold))
    }

    @Test
    fun learnedDiacriticFoldsAndEmptyAliasDrops() {
        val fold = inventoryAliases()
        assertEquals("س", applyMap("s̪", preset("varg-perso-arabic"), fold))
        assertEquals("ب", applyMap("b̥", preset("varg-perso-arabic"), fold))
        val drop = fold + ("ʌ" to "")
        assertEquals("م", applyMap("ʌ m", preset("varg-perso-arabic"), drop))
        assertEquals("ʌ m", applyMap("ʌ m", preset("ipa"), drop))
    }

    @Test
    fun lossyPersianMayCollapseSchwa() {
        val mapped = applyMap("m ə", preset("lossy-persian"))
        assertFalse(mapped.contains("ə"))
        assertFalse(mapped.contains("ٚ"))
        assertTrue(mapped.isNotBlank())
    }

    private fun preset(id: String): TranscriptMap =
        json.decodeFromString<WireMap>(presetJson(id)).toTranscriptMap()

    private fun presetJson(id: String): String {
        val resource = javaClass.classLoader?.getResourceAsStream("presets/$id.json")
        if (resource != null) {
            return resource.bufferedReader().use { it.readText() }
        }
        var dir = File(".").canonicalFile
        repeat(8) {
            val candidate = File(dir, "schemas/presets/$id.json")
            if (candidate.isFile) return candidate.readText()
            dir = dir.parentFile ?: return@repeat
        }
        error("missing preset $id (cwd=${File(".").canonicalFile})")
    }

    private fun inventoryAliases(): Map<String, String> {
        var dir = File(".").canonicalFile
        val text = run {
            var found: String? = null
            repeat(8) {
                val candidate = File(dir, "schemas/gilaki_inventory.json")
                if (candidate.isFile) {
                    found = candidate.readText()
                    return@run found
                }
                dir = dir.parentFile ?: return@repeat
            }
            error("missing gilaki inventory")
        }
        val table = json.decodeFromString<JsonObject>(text)["aliases"] as JsonObject
        return table.mapValues { (_, value) -> (value as JsonPrimitive).content }
    }
}
