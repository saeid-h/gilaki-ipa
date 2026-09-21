package com.kingstreet.gilaki.rewriter

import com.kingstreet.gilaki.data.WireMap
import com.kingstreet.gilaki.data.toTranscriptMap
import java.io.File
import kotlinx.serialization.json.Json
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
}
