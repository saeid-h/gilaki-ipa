# Android client notes

applicationId: **`com.kingstreet.gilaki`** (do not change after first install).

v1 is a thin transcriber: record or pick a file, show mapped text, optional IPA, maps and Settings on device.

## Build

From `android/`:

```bash
./gradlew :app:testDebugUnitTest
```

Unit tests cover the shared rewriter cases in `docs/product/plan.md` §12 and assert `BuildConfig.APPLICATION_ID`. They load `schemas/presets/*.json` (also copied onto the test classpath).

Do not install an APK unless the operator asks. Signing keystore is the operator’s responsibility.

## Network

Production: HTTPS only to `https://1404kingstreet.com/gilaki-api`. No API key field.

Permissions in `AndroidManifest.xml`:

```xml
<uses-permission android:name="android.permission.INTERNET" />
<uses-permission android:name="android.permission.RECORD_AUDIO" />
```

Release sets `usesCleartextTraffic="false"`. Debug merges a `network_security_config.xml` that permits cleartext for LAN / emulator tests.

Emulator → host machine API: `http://10.0.2.2:18741`  
Physical phone → LAN: `http://192.168.x.x:18741` (debug only)

## Storage

- Audio: `context.filesDir` (`take.m4a`) or cache for picked files. App-private.
- Custom maps and last IPA: DataStore preferences.
- Presets: cached JSON from `GET /v1/presets/{id}`.

Do not use MediaStore as the only copy if the user expects privacy; keep a private copy.

## Screens

Bottom bar: Record, Result, Maps, Settings (Caspian Paper teal indicator).

Changing map on Result rewrites locally from the last IPA. Do not re-upload. After a successful recognize the app opens Result.

## Recognize call

`multipart/form-data`:

- part `audio`
- optional `map_json` only if “apply this custom map on the server for this request” is on
- default: IPA from server, map on device

Recordings are AAC `.m4a`; the server ffmpeg path converts to 16 kHz mono.
