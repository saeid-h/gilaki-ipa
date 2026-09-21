# Android client notes

applicationId: **`com.kingstreet.gilaki`** (do not change after first install).

v1 is a thin transcriber: record or pick a file, show mapped text, optional IPA, maps and Settings on device.

## Network

Production: HTTPS only to `https://1404kingstreet.com/gilaki-api`. No API key field.

Debug `AndroidManifest.xml` needs:

```xml
<uses-permission android:name="android.permission.INTERNET" />
<uses-permission android:name="android.permission.RECORD_AUDIO" />
```

Do not ship `usesCleartextTraffic="true"` on release. Debug-only `network_security_config.xml` if someone tests raw LAN HTTP.

Emulator → host machine API: `http://10.0.2.2:18741`  
Physical phone → LAN: `http://192.168.x.x:18741` (debug only)

## Storage

- Audio: `context.filesDir` or `getExternalFilesDir` (app-private).
- Custom maps: DataStore JSON or Room.
- Presets: cache from `GET /v1/presets/{id}`.

Do not use MediaStore as the only copy if the user expects privacy; keep a private copy.

## Screens

Record, Result (mapped transcript + optional IPA toggle), Maps (JSON editor), Settings (API base URL only).

Changing map on Result rewrites locally from the last IPA. Do not re-upload.

## Recognize call

`multipart/form-data`:

- part `audio`
- optional `preset_id`
- optional `map_json` only if “apply this map on server for this request” is on
- default: IPA from server, map on device

Convert recordings to 16 kHz PCM WAV on device if you can; otherwise let the server ffmpeg path do it.

Signing keystore is the operator’s responsibility.
