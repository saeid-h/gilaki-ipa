package com.kingstreet.gilaki.export

import java.io.File

fun exportPaths(stem: String): Pair<String, String> {
    val base = stem.removeSuffix(".wav")
    return "$base.wav" to "$base.ipa.txt"
}

fun writePair(folder: File, stem: String, wavBytes: ByteArray, ipa: String): Pair<File, File> {
    folder.mkdirs()
    val (wavName, ipaName) = exportPaths(stem)
    val wav = File(folder, wavName)
    val ipaFile = File(folder, ipaName)
    wav.writeBytes(wavBytes)
    ipaFile.writeText(ipa.trim() + "\n")
    return wav to ipaFile
}

fun copyAudioAndIpa(folder: File, stem: String, audio: File, ipa: String): Pair<File, File> {
    folder.mkdirs()
    val ext = audio.extension.ifBlank { "wav" }
    val dest = File(folder, "$stem.$ext")
    val ipaFile = File(folder, "$stem.ipa.txt")
    audio.copyTo(dest, overwrite = true)
    ipaFile.writeText(ipa.trim() + "\n")
    return dest to ipaFile
}
