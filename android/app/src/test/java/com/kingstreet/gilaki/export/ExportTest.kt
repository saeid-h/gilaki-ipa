package com.kingstreet.gilaki.export

import java.io.File
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class ExportTest {
    @Test
    fun pairShapeIsWavAndIpaTxt() {
        val dir = File(System.getProperty("java.io.tmpdir"), "gilaki-export-test").apply {
            deleteRecursively()
            mkdirs()
        }
        val (wav, ipa) = writePair(dir, "clip-1", "RIFF".toByteArray(), "m ə ʃ")
        assertEquals("clip-1.wav", wav.name)
        assertEquals("clip-1.ipa.txt", ipa.name)
        assertTrue(wav.readBytes().contentEquals("RIFF".toByteArray()))
        assertEquals("m ə ʃ\n", ipa.readText())
        dir.deleteRecursively()
    }
}
