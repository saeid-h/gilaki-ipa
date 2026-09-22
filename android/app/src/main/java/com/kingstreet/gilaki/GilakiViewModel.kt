package com.kingstreet.gilaki

import android.app.Application
import android.content.Context
import android.media.MediaRecorder
import android.net.Uri
import android.os.Build
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.kingstreet.gilaki.BuildConfig
import com.kingstreet.gilaki.data.Prefs
import com.kingstreet.gilaki.data.WireMap
import com.kingstreet.gilaki.data.gilakiApi
import com.kingstreet.gilaki.data.toTranscriptMap
import com.kingstreet.gilaki.export.copyAudioAndIpa
import com.kingstreet.gilaki.rewriter.TranscriptMap
import com.kingstreet.gilaki.rewriter.applyMap
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.RequestBody.Companion.asRequestBody
import java.io.File

private const val DEFAULT_PRESET = "varg-perso-arabic"
private const val CUSTOM_ID = "custom"
private val json = Json { ignoreUnknownKeys = true; prettyPrint = true }

data class UiState(
    val lang: String = "en",
    val apiBase: String = BuildConfig.DEFAULT_API_BASE,
    val maps: Map<String, TranscriptMap> = emptyMap(),
    val activeId: String = DEFAULT_PRESET,
    val ipa: String = "",
    val showIpa: Boolean = false,
    val status: String = "ready",
    val error: String = "",
    val backend: String = "",
    val applyOnServer: Boolean = false,
    val customJson: String = DEFAULT_CUSTOM,
    val recording: Boolean = false,
    val showResult: Boolean = false,
    val exportNote: String = "",
)

private val DEFAULT_CUSTOM = """
{
  "id": "my-map",
  "name": "My map",
  "script": "Latn",
  "direction": "ltr",
  "lossy": false,
  "rules": [
    {"ipa": "ə", "out": "e"},
    {"ipa": "ʃ", "out": "sh"}
  ]
}
""".trimIndent()

class GilakiViewModel(app: Application) : AndroidViewModel(app) {
    private val prefs = Prefs(app)
    private val _state = MutableStateFlow(UiState())
    val state: StateFlow<UiState> = _state
    private var recorder: MediaRecorder? = null
    private val takeFile = File(app.filesDir, "take.m4a")
    private var lastAudio: File? = null

    init {
        viewModelScope.launch { boot() }
    }

    fun activeMap(): TranscriptMap? {
        val s = _state.value
        return if (s.activeId == CUSTOM_ID) customMap() else s.maps[s.activeId]
    }

    fun mappedText(): String {
        val ipa = _state.value.ipa
        if (ipa.isBlank()) return ""
        val map = activeMap() ?: return ""
        return applyMap(ipa, map)
    }

    fun setLang(lang: String) {
        _state.update { it.copy(lang = lang) }
        viewModelScope.launch { prefs.saveLang(lang) }
    }

    fun setApiBase(value: String) {
        _state.update { it.copy(apiBase = value) }
    }

    fun setCustomJson(value: String) {
        _state.update { it.copy(customJson = value) }
    }

    fun setApplyOnServer(value: Boolean) {
        _state.update { it.copy(applyOnServer = value) }
        viewModelScope.launch { prefs.saveApplyOnServer(value) }
    }

    fun selectMap(id: String) {
        _state.update { it.copy(activeId = id) }
        viewModelScope.launch { prefs.saveActiveId(id) }
    }

    fun toggleIpa() {
        _state.update { it.copy(showIpa = !it.showIpa) }
    }

    fun setIpa(value: String) {
        _state.update { it.copy(ipa = value, exportNote = "") }
        viewModelScope.launch { prefs.saveLastIpa(value) }
    }

    fun exportClip() {
        viewModelScope.launch {
            try {
                val audio = lastAudio?.takeIf { it.exists() } ?: takeFile.takeIf { it.exists() }
                    ?: error("no audio")
                val dir = File(getApplication<Application>().filesDir, "export")
                copyAudioAndIpa(dir, "take", audio, _state.value.ipa)
                _state.update { it.copy(exportNote = "ok", error = "", status = "ready") }
            } catch (err: Exception) {
                fail(err)
            }
        }
    }

    fun consumeShowResult() {
        _state.update { it.copy(showResult = false) }
    }

    fun saveSettings() {
        viewModelScope.launch {
            val base = _state.value.apiBase.trim().ifBlank { BuildConfig.DEFAULT_API_BASE }
            prefs.saveApiBase(base)
            _state.update { it.copy(apiBase = base) }
            loadPresets()
        }
    }

    fun saveCustomMap() {
        viewModelScope.launch {
            try {
                json.decodeFromString<WireMap>(_state.value.customJson)
                prefs.saveCustomMap(_state.value.customJson)
                _state.update { it.copy(status = "ready", error = "") }
            } catch (err: Exception) {
                fail(err)
            }
        }
    }

    fun toggleRecord(context: Context) {
        if (recorder != null) {
            stopRecorder()
            return
        }
        viewModelScope.launch {
            try {
                startRecorder(context)
            } catch (err: Exception) {
                fail(err)
            }
        }
    }

    fun importUri(context: Context, uri: Uri) {
        viewModelScope.launch {
            try {
                val dest = File(context.cacheDir, "pick.bin")
                context.contentResolver.openInputStream(uri)?.use { input ->
                    dest.outputStream().use { output -> input.copyTo(output) }
                } ?: error("unreadable")
                recognize(dest, dest.name)
                lastAudio = dest
            } catch (err: Exception) {
                fail(err)
            }
        }
    }

    private suspend fun boot() {
        val base = prefs.apiBase(BuildConfig.DEFAULT_API_BASE)
        _state.update {
            it.copy(
                lang = prefs.lang(),
                apiBase = base,
                applyOnServer = prefs.applyOnServer(),
                customJson = prefs.customMap() ?: DEFAULT_CUSTOM,
                ipa = prefs.lastIpa(),
                activeId = prefs.activeId(DEFAULT_PRESET),
            )
        }
        prefs.mapsCache()?.let { cached ->
            runCatching { decodeMaps(cached) }.onSuccess { maps ->
                _state.update { it.copy(maps = maps) }
            }
        }
        loadPresets()
    }

    private suspend fun loadPresets() {
        try {
            val api = gilakiApi(_state.value.apiBase)
            val list = api.presets()
            val maps = linkedMapOf<String, TranscriptMap>()
            for (row in list.presets) {
                val detail = api.preset(row.id)
                val map = detail.preset?.toTranscriptMap()?.copy(id = row.id) ?: continue
                maps[row.id] = map
            }
            prefs.saveMapsCache(json.encodeToString(maps.mapValues { it.value.toWire() }))
            _state.update { it.copy(maps = maps, status = "ready", error = "") }
        } catch (err: Exception) {
            fail(err)
        }
    }

    private fun startRecorder(context: Context) {
        takeFile.delete()
        val rec = if (Build.VERSION.SDK_INT >= 31) {
            MediaRecorder(context)
        } else {
            @Suppress("DEPRECATION")
            MediaRecorder()
        }
        rec.setAudioSource(MediaRecorder.AudioSource.MIC)
        rec.setOutputFormat(MediaRecorder.OutputFormat.MPEG_4)
        rec.setAudioEncoder(MediaRecorder.AudioEncoder.AAC)
        rec.setOutputFile(takeFile.absolutePath)
        rec.prepare()
        rec.start()
        recorder = rec
        _state.update { it.copy(recording = true, status = "recording", error = "") }
    }

    private fun stopRecorder() {
        val rec = recorder ?: return
        recorder = null
        try {
            rec.stop()
        } catch (_: Exception) {
        }
        rec.release()
        _state.update { it.copy(recording = false) }
        if (takeFile.exists() && takeFile.length() > 0) {
            viewModelScope.launch {
                try {
                    recognize(takeFile, "take.m4a")
                } catch (err: Exception) {
                    fail(err)
                }
            }
        }
    }

    private suspend fun recognize(file: File, filename: String) {
        lastAudio = file
        _state.update { it.copy(status = "uploading", error = "", exportNote = "") }
        val body = file.asRequestBody("audio/*".toMediaType())
        val audio = MultipartBody.Part.createFormData("audio", filename, body)
        val s = _state.value
        val mapPart = if (s.applyOnServer && s.activeId == CUSTOM_ID) {
            MultipartBody.Part.createFormData("map_json", s.customJson)
        } else {
            null
        }
        val data = gilakiApi(s.apiBase).recognize(audio, mapPart)
        val ipa = data.ipa.orEmpty()
        prefs.saveLastIpa(ipa)
        _state.update {
            it.copy(
                ipa = ipa,
                status = "ready",
                backend = data.backend.orEmpty(),
                error = "",
                showResult = true,
            )
        }
    }

    private fun customMap(): TranscriptMap? = runCatching {
        json.decodeFromString<WireMap>(_state.value.customJson).toTranscriptMap()
    }.getOrNull()

    private fun fail(err: Exception) {
        _state.update { it.copy(status = "error", error = err.message ?: err.toString(), recording = false) }
    }

    private fun decodeMaps(raw: String): Map<String, TranscriptMap> {
        val wires = json.decodeFromString<Map<String, WireMap>>(raw)
        return wires.mapValues { it.value.toTranscriptMap() }
    }

    private fun TranscriptMap.toWire(): WireMap = WireMap(
        id = id,
        name = name,
        script = script,
        direction = direction,
        lossy = lossy,
        normalize = normalize,
        separator = separator,
        unknown = unknown,
        rules = rules.map { com.kingstreet.gilaki.data.WireRule(it.ipa, it.out) },
    )
}
