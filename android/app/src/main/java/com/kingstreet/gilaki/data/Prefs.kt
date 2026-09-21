package com.kingstreet.gilaki.data

import android.content.Context
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map

private val Context.dataStore by preferencesDataStore("gilaki")

class Prefs(private val context: Context) {
    private val apiBase = stringPreferencesKey("apiBase")
    private val lang = stringPreferencesKey("uiLang")
    private val custom = stringPreferencesKey("customMap")
    private val applyServer = booleanPreferencesKey("applyOnServer")
    private val lastIpa = stringPreferencesKey("lastIpa")
    private val activeId = stringPreferencesKey("activeId")
    private val mapsCache = stringPreferencesKey("mapsCache")

    suspend fun apiBase(default: String): String =
        context.dataStore.data.map { it[apiBase] ?: default }.first()

    suspend fun lang(): String = context.dataStore.data.map { it[lang] ?: "en" }.first()

    suspend fun customMap(): String? = context.dataStore.data.map { it[custom] }.first()

    suspend fun applyOnServer(): Boolean =
        context.dataStore.data.map { it[applyServer] ?: false }.first()

    suspend fun lastIpa(): String = context.dataStore.data.map { it[lastIpa] ?: "" }.first()

    suspend fun activeId(default: String): String =
        context.dataStore.data.map { it[activeId] ?: default }.first()

    suspend fun mapsCache(): String? = context.dataStore.data.map { it[mapsCache] }.first()

    suspend fun saveApiBase(value: String) {
        context.dataStore.edit { it[apiBase] = value }
    }

    suspend fun saveLang(value: String) {
        context.dataStore.edit { it[lang] = value }
    }

    suspend fun saveCustomMap(value: String) {
        context.dataStore.edit { it[custom] = value }
    }

    suspend fun saveApplyOnServer(value: Boolean) {
        context.dataStore.edit { it[applyServer] = value }
    }

    suspend fun saveLastIpa(value: String) {
        context.dataStore.edit { it[lastIpa] = value }
    }

    suspend fun saveActiveId(value: String) {
        context.dataStore.edit { it[activeId] = value }
    }

    suspend fun saveMapsCache(value: String) {
        context.dataStore.edit { it[mapsCache] = value }
    }
}
