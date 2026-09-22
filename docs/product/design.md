---
version: alpha
name: Caspian-Paper
description: >
  Shared visual system for the Gilaki transcriber (web + Android).
  Light cream “paper” canvas, one Caspian teal accent, RTL-native transcript,
  IPA as a quiet optional line. Inspired by the Stitch DESIGN.md format
  (https://github.com/VoltAgent/awesome-design-md) — not a clone of Notion,
  Mintlify, or ElevenLabs.
colors:
  canvas: "#F4F0E6"
  surface: "#FBF8F1"
  surface-paper: "#FFFCF6"
  hairline: "#E4DDD0"
  hairline-strong: "#C9C0B0"
  ink: "#1C1914"
  ink-muted: "#5C574E"
  ink-faint: "#8A8478"
  ipa: "#6B6560"
  primary: "#1A6B62"
  primary-pressed: "#14564F"
  primary-soft: "#D7EBE7"
  on-primary: "#FBF8F1"
  clay: "#C45C26"
  clay-soft: "#F6E4D6"
  danger: "#B42318"
  on-dark: "#FBF8F1"
typography:
  ui:
    fontFamily: Vazirmatn
    fallback: "Noto Sans, system-ui, sans-serif"
  transcript-arab:
    fontFamily: Vazirmatn
  transcript-latn:
    fontFamily: "Source Serif 4"
    fallback: "Noto Serif, Georgia, serif"
  ipa:
    fontFamily: "Charis SIL"
    fallback: "Noto Sans, Doulos SIL, serif"
---

# DESIGN.md — Caspian Paper

One system for `web/` and Android `com.kingstreet.gilaki`. Agents must read this file before any UI work. Product behaviour stays in [`plan.md`](plan.md); this file is look and feel only.

Format follows [Google Stitch DESIGN.md](https://stitch.withgoogle.com/docs/design-md/overview/) as used in [awesome-design-md](https://github.com/VoltAgent/awesome-design-md).

---

## 1. Visual theme and atmosphere

**Name:** Caspian Paper.

**Mood:** A quiet writing desk by the Caspian — rain, tea, rice paper — not a voice-AI dashboard and not a developer IDE.

**Philosophy:** The transcript is the product. Chrome is scarce. One accent color. Plenty of paper-white space. When the active map is Arabic-script, the whole result surface is RTL without looking like a bolted-on “Arabic mode.”

**Density:** Comfortable, not compact. Mapped text is large. Controls are few.

**References (inspiration only, do not copy tokens):**

- Notion / Mastercard — warm cream, reading
- Mintlify — one green, documentation calm
- Not ElevenLabs cinematic dark (fights Perso-Arabic reading)
- Not Linear / Vercel black chrome (engineer product)
- Not Material default purple on Android

**Atmosphere words:** paper, tea, rain, teal, ink, quiet, bilingual.

---

## 2. Color palette and roles

Use these hex values on web (CSS variables) and Android (Material 3 roles). Do not introduce a second accent.

| Token | Hex | Role |
|---|---|---|
| `canvas` | `#F4F0E6` | Page / activity background |
| `surface` | `#FBF8F1` | Toolbars, sheets, settings rows |
| `surface-paper` | `#FFFCF6` | Transcript card (slightly brighter than canvas) |
| `hairline` | `#E4DDD0` | Borders, chip outlines |
| `hairline-strong` | `#C9C0B0` | Focus rings, pressed outlines |
| `ink` | `#1C1914` | Body, mapped transcript |
| `ink-muted` | `#5C574E` | Labels, secondary copy |
| `ink-faint` | `#8A8478` | Captions, timestamps we do not show in v1 |
| `ipa` | `#6B6560` | Optional IPA line only |
| `primary` | `#1A6B62` | Record, primary buttons, selected chip, links |
| `primary-pressed` | `#14564F` | Pressed / recording |
| `primary-soft` | `#D7EBE7` | Selected chip fill, focus wash |
| `on-primary` | `#FBF8F1` | Text/icon on teal |
| `clay` | `#C45C26` | Lossy-map warning (not error) |
| `clay-soft` | `#F6E4D6` | Lossy banner background |
| `danger` | `#B42318` | Destructive only (delete custom map) |

Android Material 3 mapping:

- `primary` → `primary`
- `on-primary` → `onPrimary`
- `canvas` → `background`
- `surface` / `surface-paper` → `surface` / `surfaceContainerLowest`
- `ink` → `onBackground` / `onSurface`
- `error` → `danger`

No dark theme in v1. Do not auto-follow system night mode (Perso-Arabic on dark is a later revision).

---

## 3. Typography rules

Load **Vazirmatn** (UI + Arabic transcript), **Source Serif 4** (Latin / academic mapped text), **Charis SIL** or Noto Sans (IPA). Self-host or Google Fonts. Android v1 uses the system sans (Noto Arabic fallback) for UI and Arab maps and the system serif for Latin maps, with IPA in the same face; do not use Inter or Tahoma.

| Role | Face | Size | Weight | Line height | Notes |
|---|---|---|---|---|---|
| App title | Vazirmatn | 22 / 28 | 600 | 1.2 | “Gilaki” not a marketing hero |
| Section label | Vazirmatn | 13 | 500 | 1.3 | Uppercase Latin ok; Arabic sentence case |
| Mapped transcript Arab | Vazirmatn | 28–34 | 500 | 1.7 | RTL, the visual hero |
| Mapped transcript Latn | Source Serif 4 | 26–32 | 400 | 1.55 | LTR |
| IPA | Charis SIL | 16 | 400 | 1.5 | Hidden until toggle; never larger than mapped text |
| Body / settings | Vazirmatn | 16 | 400 | 1.5 | |
| Chip / button | Vazirmatn | 14–16 | 500 | 1.2 | |
| JSON editor | ui-monospace / JetBrains Mono | 13 | 400 | 1.45 | Maps screen only |

Do not use Inter as the brand face. Do not fake Arabic with Tahoma.

---

## 4. Component stylings

**Record (primary CTA):** 72–88px circle, fill `primary`, icon `on-primary` (mic). Recording: `primary-pressed`, gentle pulse (scale 1.0–1.04, 900ms), no neon glow. Secondary: text button “Choose file” in `ink-muted`.

**Transcript card:** `surface-paper`, radius 16px, hairline 1px, padding 20–24px. Mapped text is the only large type on the card. Map name as a small chip above or below, not a title competing with the transcript.

**Map chips:** pill, height 36px, unselected = canvas + hairline + ink; selected = `primary-soft` fill + `primary` text. Lossy chip shows a small clay dot.

**IPA disclosure:** text control “Show IPA” / hide; IPA appears under the transcript in `ipa` color, never bold. An **IPA** map chip shows the same phones as the large card. After v1, the IPA line is an editor so a speaker can correct phones; mapped text still remaps locally.

**Export:** ghost control “Export wav + IPA”. Files stay on the device.

**Lossy banner:** `clay-soft` background, `clay` label, one line: this map collapses Gilaki vowels.

**Inputs:** 12px radius, canvas fill, hairline border; focus = 2px `primary`. Settings URL field is full width.

**JSON editor:** full-width, monospace, canvas inset, min-height 12rem. Not on the Record/Result hero.

**Navigation:** Web — top bar (title + Settings). Android — four destinations: Record, Result, Maps, Settings (bottom bar, teal indicator). Result may be stacked after a recording instead of a persistent tab.

**Buttons:** Primary filled teal; secondary ghost (no fill, ink). No gradients. No drop-shadow on buttons.

---

## 5. Layout principles

Spacing scale (8pt): 4, 8, 12, 16, 24, 32, 48.

Web: single column, max-width 40rem (640px) centered on canvas. This is a tool, not a marketing landing page.

Android: edge padding 16dp; transcript card full width minus 16dp.

Vertical rhythm on Record: title, then flexible space, then mic, then file action, then quiet status.

Result: map chips → transcript card → IPA toggle → optional error.

RTL: `direction` follows the **active map**, not the OS language. Arabic maps flip the transcript card and chip row. Settings may stay LTR if the operator UI is English; v1 English chrome is acceptable if the transcript itself RTL-flips.

---

## 6. Depth and elevation

Almost flat. Transcript card may use a single shadow: `0 1px 2px rgba(28,25,20,0.06), 0 8px 24px rgba(28,25,20,0.04)`. No stacked elevation system. Android: `surface` tint, not 8dp FAB shadow on everything. The mic is a filled circle, not a Material FAB with a scrim.

---

## 7. Do’s and don’ts

**Do**

- Make mapped text the largest thing on Result
- Use one teal
- Flip layout for `direction: rtl` maps
- Warn on `lossy: true` with clay, not red
- Keep IPA smaller and optional
- Match web and Android spacing, radius, and color hex

**Don’t**

- Dark mode in v1
- Purple, electric lime, or waveform-hero chrome
- Inter / Roboto as the personality
- Put the JSON map editor on the recording screen
- Show API key fields
- Invent word-boundary chips or “AI sparkle” icons
- Use red for lossy maps
- Center-align long Arabic transcripts (right-align in RTL)

---

## 8. Responsive behavior

| Width | Behavior |
|---|---|
| < 480px | Single column, mic 72px, transcript 28px |
| 480–720px | Mic 80px, transcript 32px, max-width 40rem |
| > 720px | Same column, more side canvas; do not add a second column of marketing |

Touch targets ≥ 44px (web) / 48dp (Android). Chip rows wrap.

Playwright should assert mapped text is visible and larger than the IPA node when IPA is shown.

---

## 9. Agent prompt guide

Quick tokens: canvas `#F4F0E6`, paper `#FFFCF6`, ink `#1C1914`, teal `#1A6B62`, clay `#C45C26`.

Ready prompt:

> Build the Gilaki transcriber UI using docs/product/design.md (Caspian Paper). Cream canvas, one teal record button, mapped transcript as a large paper card, IPA behind a disclosure. Vazirmatn, RTL when the map is Arab. No dark mode, no API key field, no JSON editor on the result hero. Web and Android must share these tokens.

---

## 10. Screens (both clients)

1. **Record** — title, mic, choose file, short status (ready / uploading / error)
2. **Result** — chips for presets, paper card (mapped), optional IPA (editable in the quality loop), lossy banner if needed, export `wav` + `ipa.txt` locally
3. **Maps** — custom JSON editor, save locally
4. **Settings** — API base URL; UI language English (default) or Persian. No API key.

Changing a chip on Result remaps locally and updates the card; do not flash a full-page loader.
