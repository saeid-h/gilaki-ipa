package com.kingstreet.gilaki.ui

import android.Manifest
import android.content.pm.PackageManager
import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.GraphicEq
import androidx.compose.material.icons.outlined.Mic
import androidx.compose.material.icons.outlined.Settings
import androidx.compose.material.icons.outlined.Stop
import androidx.compose.material.icons.outlined.Tune
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.FilterChip
import androidx.compose.material3.FilterChipDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.NavigationBarItemDefaults
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalLayoutDirection
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.LayoutDirection
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import com.kingstreet.gilaki.GilakiViewModel
import com.kingstreet.gilaki.UiState

@Composable
fun GilakiApp(vm: GilakiViewModel = viewModel()) {
    val state by vm.state.collectAsStateWithLifecycle()
    val chromeDir = if (state.lang == "fa") LayoutDirection.Rtl else LayoutDirection.Ltr
    CaspianTheme {
        CompositionLocalProvider(LocalLayoutDirection provides chromeDir) {
            GilakiScaffold(state = state, vm = vm)
        }
    }
}

@Composable
private fun GilakiScaffold(state: UiState, vm: GilakiViewModel) {
    val copy = copy(state.lang)
    val context = LocalContext.current
    var selected by remember { mutableStateOf("record") }
    val pick = rememberLauncherForActivityResult(ActivityResultContracts.GetContent()) { uri: Uri? ->
        if (uri != null) vm.importUri(context, uri)
    }
    val permission = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        if (granted) vm.toggleRecord(context)
    }

    LaunchedEffect(state.showResult) {
        if (state.showResult) {
            selected = "result"
            vm.consumeShowResult()
        }
    }

    Scaffold(
        containerColor = Canvas,
        bottomBar = {
            NavigationBar(containerColor = SurfaceBar) {
                NavigationBarItem(
                    selected = selected == "record",
                    onClick = { selected = "record" },
                    icon = { Icon(Icons.Outlined.Mic, contentDescription = copy.record) },
                    label = { Text(copy.record) },
                    colors = navColors(),
                )
                NavigationBarItem(
                    selected = selected == "result",
                    onClick = { selected = "result" },
                    icon = { Icon(Icons.Outlined.GraphicEq, contentDescription = copy.title) },
                    label = { Text(copy.title) },
                    colors = navColors(),
                )
                NavigationBarItem(
                    selected = selected == "maps",
                    onClick = { selected = "maps" },
                    icon = { Icon(Icons.Outlined.Tune, contentDescription = copy.maps) },
                    label = { Text(copy.maps) },
                    colors = navColors(),
                )
                NavigationBarItem(
                    selected = selected == "settings",
                    onClick = { selected = "settings" },
                    icon = { Icon(Icons.Outlined.Settings, contentDescription = copy.settings) },
                    label = { Text(copy.settings) },
                    colors = navColors(),
                )
            }
        },
    ) { padding ->
        when (selected) {
            "record" -> RecordPane(
                state,
                copy,
                padding,
                onRecord = {
                    if (state.recording) {
                        vm.toggleRecord(context)
                    } else if (
                        ContextCompat.checkSelfPermission(context, Manifest.permission.RECORD_AUDIO) ==
                        PackageManager.PERMISSION_GRANTED
                    ) {
                        vm.toggleRecord(context)
                    } else {
                        permission.launch(Manifest.permission.RECORD_AUDIO)
                    }
                },
                onFile = { pick.launch("audio/*") },
            )
            "result" -> ResultPane(state, copy, padding, vm)
            "maps" -> MapsPane(state, copy, padding, vm)
            else -> SettingsPane(state, copy, padding, vm)
        }
    }
}

@Composable
private fun navColors() = NavigationBarItemDefaults.colors(
    selectedIconColor = Primary,
    selectedTextColor = Primary,
    indicatorColor = PrimarySoft,
    unselectedIconColor = InkMuted,
    unselectedTextColor = InkMuted,
)

@Composable
private fun RecordPane(
    state: UiState,
    copy: Copy,
    padding: PaddingValues,
    onRecord: () -> Unit,
    onFile: () -> Unit,
) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(padding)
            .padding(24.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Text(copy.title, fontSize = 22.sp, fontWeight = FontWeight.SemiBold, color = Ink)
        Spacer(Modifier.height(8.dp))
        Text(copy.subtitle, color = InkMuted)
        Spacer(Modifier.weight(1f))
        Button(
            onClick = onRecord,
            modifier = Modifier.size(80.dp),
            shape = CircleShape,
            contentPadding = PaddingValues(0.dp),
            colors = ButtonDefaults.buttonColors(
                containerColor = if (state.recording) PrimaryPressed else Primary,
                contentColor = OnPrimary,
            ),
        ) {
            Icon(
                imageVector = if (state.recording) Icons.Outlined.Stop else Icons.Outlined.Mic,
                contentDescription = if (state.recording) copy.stop else copy.record,
                modifier = Modifier.size(32.dp),
            )
        }
        TextButton(onClick = onFile) {
            Text(copy.chooseFile, color = InkMuted)
        }
        val status = when (state.status) {
            "recording" -> copy.recording
            "uploading" -> copy.uploading
            "error" -> state.error.ifBlank { copy.error }
            else -> listOf(copy.ready, state.backend).filter { it.isNotBlank() }.joinToString(" · ")
        }
        Text(status, color = if (state.status == "error") Danger else InkFaint, fontSize = 13.sp)
        Spacer(Modifier.weight(1f))
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun ResultPane(state: UiState, copy: Copy, padding: PaddingValues, vm: GilakiViewModel) {
    val map = vm.activeMap()
    val rtl = map?.direction == "rtl"
    val mapped = vm.mappedText().ifBlank { copy.noResult }
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(padding)
            .padding(16.dp)
            .verticalScroll(rememberScrollState()),
    ) {
        FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            state.maps.forEach { (id, item) ->
                Chip(item.name ?: id, selected = state.activeId == id, lossy = item.lossy) {
                    vm.selectMap(id)
                }
            }
            Chip("Custom", selected = state.activeId == CUSTOM_CHIP, lossy = false) {
                vm.selectMap(CUSTOM_CHIP)
            }
        }
        if (map?.lossy == true) {
            Spacer(Modifier.height(12.dp))
            Text(
                copy.lossy,
                modifier = Modifier
                    .fillMaxWidth()
                    .clip(RoundedCornerShape(12.dp))
                    .background(ClaySoft)
                    .padding(12.dp),
                color = Clay,
                fontSize = 14.sp,
            )
        }
        Spacer(Modifier.height(16.dp))
        CompositionLocalProvider(
            LocalLayoutDirection provides if (rtl) LayoutDirection.Rtl else LayoutDirection.Ltr,
        ) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .clip(RoundedCornerShape(16.dp))
                    .background(SurfacePaper)
                    .border(1.dp, Hairline, RoundedCornerShape(16.dp))
                    .padding(24.dp),
            ) {
                val isArab = map?.script == "Arab"
                val isIpa = map?.id == "ipa" || map?.script == "Zyyy"
                Text(
                    mapped,
                    color = if (isIpa) IpaColor else Ink,
                    fontSize = if (isArab) 32.sp else if (isIpa) 22.sp else 28.sp,
                    fontWeight = if (isArab) FontWeight.Medium else FontWeight.Normal,
                    fontFamily = when {
                        isArab -> FontFamily.SansSerif
                        isIpa -> FontFamily.SansSerif
                        else -> FontFamily.Serif
                    },
                    lineHeight = if (isArab) 44.sp else 36.sp,
                )
                if (state.showIpa) {
                    Spacer(Modifier.height(16.dp))
                    CompositionLocalProvider(LocalLayoutDirection provides LayoutDirection.Ltr) {
                        OutlinedTextField(
                            value = state.ipa,
                            onValueChange = vm::setIpa,
                            modifier = Modifier.fillMaxWidth(),
                            label = { Text(copy.saveSounds) },
                            textStyle = TextStyle(fontSize = 16.sp, color = IpaColor),
                        )
                    }
                }
            }
        }
        TextButton(onClick = { vm.toggleIpa() }) {
            Text(if (state.showIpa) copy.hideSounds else copy.showSounds, color = Ink)
        }
        if (state.ipa.isNotBlank()) {
            TextButton(onClick = { vm.exportClip() }) {
                Text(copy.exportPair, color = Ink)
            }
        }
        if (state.exportNote == "ok") {
            Text(copy.exported, color = InkFaint, fontSize = 13.sp)
        }
    }
}

private const val CUSTOM_CHIP = "custom"

@Composable
private fun Chip(label: String, selected: Boolean, lossy: Boolean, onClick: () -> Unit) {
    FilterChip(
        selected = selected,
        onClick = onClick,
        label = {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(label)
                if (lossy) {
                    Spacer(Modifier.size(8.dp))
                    Box(
                        Modifier
                            .size(8.dp)
                            .clip(CircleShape)
                            .background(Clay),
                    )
                }
            }
        },
        colors = FilterChipDefaults.filterChipColors(
            selectedContainerColor = PrimarySoft,
            selectedLabelColor = Primary,
            containerColor = Canvas,
            labelColor = Ink,
        ),
        border = FilterChipDefaults.filterChipBorder(
            enabled = true,
            selected = selected,
            borderColor = Hairline,
            selectedBorderColor = PrimarySoft,
        ),
    )
}

@Composable
private fun MapsPane(state: UiState, copy: Copy, padding: PaddingValues, vm: GilakiViewModel) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(padding)
            .padding(16.dp)
            .verticalScroll(rememberScrollState()),
    ) {
        Text(copy.customMap, color = InkMuted, fontWeight = FontWeight.Medium)
        Text(copy.customHint, color = InkFaint, fontSize = 13.sp)
        Spacer(Modifier.height(8.dp))
        OutlinedTextField(
            value = state.customJson,
            onValueChange = vm::setCustomJson,
            modifier = Modifier
                .fillMaxWidth()
                .height(220.dp),
            textStyle = TextStyle(fontFamily = FontFamily.Monospace, fontSize = 13.sp),
        )
        Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(top = 12.dp)) {
            Switch(checked = state.applyOnServer, onCheckedChange = vm::setApplyOnServer)
            Text(copy.applyServer, modifier = Modifier.padding(start = 8.dp), color = Ink)
        }
        Button(onClick = vm::saveCustomMap, colors = ButtonDefaults.buttonColors(containerColor = Primary)) {
            Text(copy.saveMap)
        }
        if (state.status == "error") {
            Spacer(Modifier.height(12.dp))
            Text(state.error.ifBlank { copy.error }, color = Danger, fontSize = 13.sp)
        }
    }
}

@Composable
private fun SettingsPane(state: UiState, copy: Copy, padding: PaddingValues, vm: GilakiViewModel) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(padding)
            .padding(16.dp),
    ) {
        Text(copy.apiBase, color = InkMuted, fontWeight = FontWeight.Medium)
        OutlinedTextField(
            value = state.apiBase,
            onValueChange = vm::setApiBase,
            modifier = Modifier.fillMaxWidth(),
        )
        Spacer(Modifier.height(16.dp))
        Text(copy.language, color = InkMuted, fontWeight = FontWeight.Medium)
        Row(verticalAlignment = Alignment.CenterVertically) {
            RadioButton(selected = state.lang == "en", onClick = { vm.setLang("en") })
            Text(copy.english)
            RadioButton(selected = state.lang == "fa", onClick = { vm.setLang("fa") })
            Text(copy.persian)
        }
        Button(onClick = vm::saveSettings, colors = ButtonDefaults.buttonColors(containerColor = Primary)) {
            Text(copy.saveSettings)
        }
    }
}
