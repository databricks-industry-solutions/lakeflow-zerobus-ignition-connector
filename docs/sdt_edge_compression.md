## Edge compression: Deadband vs SDT (PI-like)

This module supports **edge-side numeric compression** to reduce tag event volume before sending to Zerobus/Delta.

### Modes

Configured by `numericCompressionMode`:

- `NONE`: send all values (no filtering).
- `DEADBAND`: send numeric values only when \(|Δ| > deadband\). Non-numeric values use “only on change”.
- `SDT`: **Swinging Door Trending (SDT)** with:
  - **deviation** (engineering units)
  - **max interval** (ms) forcing (optional)

### PI-like SDT semantics (high level)

For each numeric tag, SDT maintains a “door” (line segment) anchored at the last emitted point with an error band of ±deviation. While subsequent samples stay within that band, nothing is emitted. When a new sample would violate the band, the module emits the **previous** sample as the closing point, resets, and continues.

If `maxIntervalMs > 0`, the module forces an emit at least every `maxIntervalMs` even if the signal is flat/noisy-within-band.

### Global defaults

Use these global fields (applies when no per-tag rule matches):

- `numericCompressionMode`: `NONE | DEADBAND | SDT`
- `numericDeadband`: (DEADBAND) absolute difference threshold
- `numericSdtDeviation`: (SDT) deviation (must be > 0)
- `numericSdtMaxIntervalMs`: (SDT) force-emit interval (0 disables)

### Per-tag defaults (recommended)

Use `numericCompressionRules` with **first match wins**. This is the “signal-type defaults” approach (temp vs pressure vs flow), typically implemented with tag path naming conventions or provider segmentation.

Example (illustrative):

```json
{
  "numericCompressionMode": "SDT",
  "numericSdtDeviation": 0.5,
  "numericSdtMaxIntervalMs": 600000,
  "numericCompressionRules": [
    {
      "tagPathRegex": ".*(Temp|Temperature|_C$|/Temp/).*",
      "mode": "SDT",
      "sdtDeviation": 0.2,
      "sdtMaxIntervalMs": 600000
    },
    {
      "tagPathRegex": ".*(Pressure|_bar$|_kPa$|/Pressure/).*",
      "mode": "SDT",
      "sdtDeviation": 0.05,
      "sdtMaxIntervalMs": 300000
    },
    {
      "tagPathRegex": ".*(Flow|_m3h$|/Flow/).*",
      "mode": "SDT",
      "sdtDeviation": 2.0,
      "sdtMaxIntervalMs": 300000
    }
  ]
}
```

### Backward compatibility

Older configs that only set:

- `onlyOnChange=true`
- `numericDeadband=...`

will continue to behave like `numericCompressionMode=DEADBAND` unless `numericCompressionMode` is explicitly set.

