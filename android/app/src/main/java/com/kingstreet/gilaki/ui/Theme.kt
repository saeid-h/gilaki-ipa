package com.kingstreet.gilaki.ui

import androidx.compose.material3.ColorScheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

val Canvas = Color(0xFFF4F0E6)
val SurfacePaper = Color(0xFFFFFCF6)
val SurfaceBar = Color(0xFFFBF8F1)
val Hairline = Color(0xFFE4DDD0)
val Ink = Color(0xFF1C1914)
val InkMuted = Color(0xFF5C574E)
val InkFaint = Color(0xFF8A8478)
val IpaColor = Color(0xFF6B6560)
val Primary = Color(0xFF1A6B62)
val PrimaryPressed = Color(0xFF14564F)
val PrimarySoft = Color(0xFFD7EBE7)
val OnPrimary = Color(0xFFFBF8F1)
val Clay = Color(0xFFC45C26)
val ClaySoft = Color(0xFFF6E4D6)
val Danger = Color(0xFFB42318)

private val CaspianScheme: ColorScheme = lightColorScheme(
    primary = Primary,
    onPrimary = OnPrimary,
    secondary = Clay,
    onSecondary = OnPrimary,
    background = Canvas,
    onBackground = Ink,
    surface = SurfaceBar,
    onSurface = Ink,
    surfaceContainerLowest = SurfacePaper,
    error = Danger,
    outline = Hairline,
)

@Composable
fun CaspianTheme(content: @Composable () -> Unit) {
    MaterialTheme(colorScheme = CaspianScheme, content = content)
}
